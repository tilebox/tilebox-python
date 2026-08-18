import typing
from base64 import b64decode, b64encode
from dataclasses import fields, is_dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import PurePath
from types import NoneType, UnionType
from typing import Any, get_args, get_origin
from zoneinfo import ZoneInfo

import msgspec
from google.protobuf.message import Message

from tilebox.workflows._codec import registry


def encode_json_field(value: Any, owner_type: type, field_name: str) -> bytes:
    field_type, requires_override = _encode_plan(owner_type)[field_name]
    prepared = _prepare_encode(field_type, value) if requires_override else value
    return _encode(prepared, value)


def encode_json_fields(value: Any, included_fields: list[Any]) -> bytes:
    plan = _encode_plan(type(value))
    prepared = {
        field.name: (
            _prepare_encode(plan[field.name][0], getattr(value, field.name))
            if plan[field.name][1]
            else getattr(value, field.name)
        )
        for field in included_fields
    }
    return _encode(prepared, value)


def _encode(prepared: Any, original: Any) -> bytes:
    try:
        return _JSON_ENCODER.encode(prepared)
    except (TypeError, NotImplementedError):
        _raise_encoding_error(original, path="$")
        raise


def decode_json(data: bytes, field_type: Any) -> Any:
    if not _requires_override(field_type):
        return _typed_decoder(field_type).decode(data)
    return _decode_override(field_type, _JSON_DECODER.decode(data))


@lru_cache
def _type_hints(field_type: type) -> dict[str, Any]:
    return typing.get_type_hints(field_type, include_extras=True)


@lru_cache
def _encode_plan(field_type: type) -> dict[str, tuple[Any, bool]]:
    type_hints = _type_hints(field_type)
    return {
        field.name: (
            annotation := type_hints.get(field.name, field.type),
            _requires_encode_override(annotation),
        )
        for field in fields(field_type)
    }


@lru_cache
def _requires_encode_override(field_type: Any) -> bool:
    return _requires_encode_override_inner(field_type, frozenset())


def _requires_encode_override_inner(field_type: Any, seen: frozenset[Any]) -> bool:  # noqa: PLR0911
    if field_type in seen:
        return False
    seen |= {field_type}

    origin = get_origin(field_type)
    args = get_args(field_type)
    if origin is typing.Annotated:
        return _requires_encode_override_inner(args[0], seen)
    if origin in (typing.Union, UnionType, list, tuple, dict, set, frozenset):
        return any(arg is not Ellipsis and _requires_encode_override_inner(arg, seen) for arg in args)
    if not isinstance(field_type, type):
        return False
    if issubclass(field_type, datetime):
        return True

    codec = registry.find(field_type)
    if codec is not None and codec.overrides_native:
        return True
    if not is_dataclass(field_type):
        return False
    return any(field.metadata.get("skip_serialization", False) for field in fields(field_type)) or any(
        _requires_encode_override_inner(annotation, seen) for annotation in _type_hints(field_type).values()
    )


def _prepare_encode(field_type: Any, value: Any) -> Any:  # noqa: C901, PLR0911
    if not _requires_encode_override(field_type):
        return value

    origin = get_origin(field_type)
    args = get_args(field_type)
    if origin is typing.Annotated:
        return _prepare_encode(args[0], value)
    if origin in (typing.Union, UnionType):
        if value is None:
            return None
        member = next((member for member in args if _matches_annotation(member, value)), None)
        return _prepare_encode(member, value) if member is not None else value

    if isinstance(field_type, type):
        codec = registry.find(field_type)
        if codec is not None and codec.overrides_native:
            return codec.encode(value)
        if is_dataclass(field_type):
            type_hints = _type_hints(field_type)
            return {
                field.name: _prepare_encode(type_hints.get(field.name, field.type), getattr(value, field.name))
                for field in fields(value)
                if not field.metadata.get("skip_serialization", False)
            }
        if issubclass(field_type, datetime):
            return value.isoformat()

    if origin in (list, set, frozenset) and len(args) == 1:
        return [_prepare_encode(args[0], item) for item in value]
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return [_prepare_encode(args[0], item) for item in value]
        return [_prepare_encode(item_type, item) for item_type, item in zip(args, value, strict=True)]
    if origin is dict and len(args) == 2:
        return {key: _prepare_encode(args[1], item) for key, item in value.items()}
    return value


def _matches_annotation(field_type: Any, value: Any) -> bool:
    origin = get_origin(field_type)
    if origin is typing.Annotated:
        return _matches_annotation(get_args(field_type)[0], value)
    if origin in (list, tuple, dict, set, frozenset):
        return isinstance(value, origin)
    return isinstance(field_type, type) and isinstance(value, field_type)


def _encode_hook(value: Any) -> Any:
    if isinstance(value, Message):
        return b64encode(value.SerializeToString()).decode("ascii")
    codec = registry.find(type(value))
    if codec is not None:
        return codec.encode(value)
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, ZoneInfo):
        return value.key
    raise NotImplementedError(f"Objects of type {type(value).__module__}.{type(value).__qualname__} are not supported")


def _raise_encoding_error(value: Any, path: str) -> None:  # noqa: C901
    if isinstance(value, Message):
        return

    codec = registry.find(type(value))
    if codec is not None:
        _raise_encoding_error(codec.encode(value), path)
        return

    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            if not field.metadata.get("skip_serialization", False):
                _raise_encoding_error(getattr(value, field.name), f"{path}.{field.name}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _raise_encoding_error(item, f"{path}.{key}")
        return
    if isinstance(value, list | tuple | set | frozenset):
        for index, item in enumerate(value):
            _raise_encoding_error(item, f"{path}[{index}]")
        return

    try:
        _JSON_ENCODER.encode(value)
    except (TypeError, NotImplementedError) as error:
        raise TypeError(f"{error} at {path}") from error


@lru_cache
def _typed_decoder(field_type: Any) -> msgspec.json.Decoder:
    return msgspec.json.Decoder(type=field_type, dec_hook=_decode_hook, strict=True)


def _decode_hook(field_type: type, value: Any) -> Any:
    if _is_protobuf_type(field_type):
        return field_type.FromString(b64decode(value))  # ty: ignore[unresolved-attribute]
    codec = registry.find(field_type)
    if codec is not None:
        return codec.decode(value)
    if issubclass(field_type, PurePath):
        return field_type(value)
    if field_type is ZoneInfo:
        return ZoneInfo(value)
    raise NotImplementedError(f"Objects of type {field_type.__module__}.{field_type.__qualname__} are not supported")


@lru_cache
def _requires_override(field_type: Any) -> bool:
    return _requires_override_inner(field_type, frozenset())


def _requires_override_inner(field_type: Any, seen: frozenset[Any]) -> bool:  # noqa: PLR0911
    if field_type in seen:
        return False
    seen |= {field_type}

    origin = get_origin(field_type)
    args = get_args(field_type)
    if origin is typing.Annotated:
        return _requires_override_inner(args[0], seen)
    if origin in (typing.Union, UnionType, list, tuple, dict, set, frozenset):
        return any(arg is not Ellipsis and _requires_override_inner(arg, seen) for arg in args)
    if not isinstance(field_type, type):
        return False
    if _is_protobuf_type(field_type):
        return False

    codec = registry.find(field_type)
    if codec is not None and codec.overrides_native:
        return True
    if not is_dataclass(field_type):
        return False
    return any(
        _requires_override_inner(annotation, seen)
        for annotation in typing.get_type_hints(field_type, include_extras=True).values()
    )


def _decode_override(field_type: Any, value: Any) -> Any:  # noqa: C901, PLR0911
    origin = get_origin(field_type)
    args = get_args(field_type)
    if origin is typing.Annotated:
        return _decode_override(args[0], value)
    if origin in (typing.Union, UnionType):
        if value is None and NoneType in args:
            return None
        return _decode_union([arg for arg in args if arg is not NoneType], value)

    if isinstance(field_type, type):
        codec = registry.find(field_type)
        if codec is not None and codec.overrides_native:
            return codec.decode(value)
        if is_dataclass(field_type):
            return _decode_dataclass(field_type, value)

    if origin is list and len(args) == 1:
        return [_decode_override(args[0], item) for item in msgspec.convert(value, type=list)]
    if origin is tuple:
        items = msgspec.convert(value, type=list)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode_override(args[0], item) for item in items)
        if len(items) != len(args):
            raise msgspec.ValidationError(f"Expected `array` of length {len(args)}, got {len(items)}")
        return tuple(_decode_override(item_type, item) for item_type, item in zip(args, items, strict=True))
    if origin is dict and len(args) == 2:
        mapping = msgspec.convert(value, type=dict)
        keys = _decode_dict_keys(args[0], mapping)
        return {key: _decode_override(args[1], item) for key, item in zip(keys, mapping.values(), strict=True)}
    if origin in (set, frozenset) and len(args) == 1:
        items = (_decode_override(args[0], item) for item in msgspec.convert(value, type=list))
        return origin(items)
    return msgspec.convert(value, type=field_type, dec_hook=_decode_hook, strict=True)


def _decode_dataclass(field_type: type, value: Any) -> Any:
    params = msgspec.convert(value, type=dict)
    type_hints = typing.get_type_hints(field_type, include_extras=True)
    known_fields = {field.name: field for field in fields(field_type)}
    converted = {
        name: _decode_override(type_hints.get(name, known_fields[name].type), item)
        for name, item in params.items()
        if name in known_fields
    }
    return field_type(**converted)


def _decode_dict_keys(key_type: Any, mapping: dict[Any, Any]) -> list[Any]:
    encoded = _JSON_ENCODER.encode(dict.fromkeys(mapping))
    decoded = _typed_decoder(dict[key_type, NoneType]).decode(encoded)
    return list(decoded)


def _decode_union(members: list[Any], value: Any) -> Any:
    errors: list[Exception] = []
    for member in members:
        try:
            return _decode_override(member, value)
        except (TypeError, ValueError, msgspec.ValidationError) as error:  # noqa: PERF203
            errors.append(error)
    raise msgspec.ValidationError(f"Value does not match any type in the union: {errors[-1]}")


def _is_protobuf_type(field_type: type) -> bool:
    return issubclass(field_type, Message)


_JSON_ENCODER = msgspec.json.Encoder(enc_hook=_encode_hook)
_JSON_DECODER = msgspec.json.Decoder()
