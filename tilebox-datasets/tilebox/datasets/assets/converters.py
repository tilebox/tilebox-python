"""Decorator-based conversion of protobuf messages to immutable Python values."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from datetime import timezone
from types import MappingProxyType
from typing import Any

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message


@dataclass(frozen=True, slots=True)
class _Conversion:
    python_type: type[Any]
    rename_fields: Mapping[str, str]
    field_converters: Mapping[str, Callable[[Any], Any]]


class ProtobufConverterRegistry:
    """Registry mapping generated protobuf classes to immutable Python dataclasses."""

    def __init__(self) -> None:
        self._conversions: dict[type[Message], _Conversion] = {}
        self._conversions_by_name: dict[str, _Conversion] = {}

    def register(
        self,
        protobuf_type: type[Message],
        *,
        rename_fields: Mapping[str, str] | None = None,
        field_converters: Mapping[str, Callable[[Any], Any]] | None = None,
    ) -> Any:
        """Register a decorated dataclass as the conversion target for a protobuf type."""

        def decorator(python_type: type[Any]) -> type[Any]:
            conversion = _Conversion(
                python_type,
                MappingProxyType(dict(rename_fields or {})),
                MappingProxyType(dict(field_converters or {})),
            )
            self._conversions[protobuf_type] = conversion
            self._conversions_by_name[protobuf_type.DESCRIPTOR.full_name] = conversion
            return python_type

        return decorator

    def convert(self, message: Message) -> Any:  # noqa: C901, PLR0912
        """Recursively convert a registered protobuf message."""
        full_name = message.DESCRIPTOR.full_name
        if full_name == "google.protobuf.Timestamp":
            return message.ToDatetime(tzinfo=timezone.utc)  # type: ignore[attr-defined]
        if full_name in {"google.protobuf.Struct", "google.protobuf.Value"}:
            return _freeze(MessageToDict(message))

        conversion = self._conversions.get(type(message))
        if conversion is None:
            conversion = next(
                (
                    registered
                    for protobuf_type, registered in self._conversions.items()
                    if isinstance(message, protobuf_type)
                ),
                None,
            )
        if conversion is None:
            conversion = self._conversions_by_name.get(full_name)
        if conversion is None:
            raise TypeError(f"no Python converter is registered for {full_name}")

        python_fields = {item.name for item in fields(conversion.python_type)}
        values: dict[str, Any] = {}
        for field in message.DESCRIPTOR.fields:
            name = conversion.rename_fields.get(field.name, field.name)
            if name not in python_fields:
                continue
            value = getattr(message, field.name)
            field_converter = conversion.field_converters.get(field.name)
            if field_converter is not None:
                values[name] = field_converter(value)
                continue
            if field.is_repeated:
                if field.message_type and field.message_type.GetOptions().map_entry:
                    values[name] = MappingProxyType(
                        {key: self.convert(item) if isinstance(item, Message) else item for key, item in value.items()}
                    )
                elif field.type == FieldDescriptor.TYPE_ENUM:
                    values[name] = tuple(_enum_name(field, item) for item in value)
                else:
                    values[name] = tuple(self.convert(item) if isinstance(item, Message) else item for item in value)
                continue
            if not _has_field(message, field.name) and field.type != FieldDescriptor.TYPE_ENUM:
                values.setdefault(name, None)
            elif field.type == FieldDescriptor.TYPE_MESSAGE:
                values[name] = self.convert(value)
            elif field.type == FieldDescriptor.TYPE_ENUM:
                values[name] = _enum_name(field, value)
            else:
                values[name] = value
        return conversion.python_type(**values)


def _has_field(message: Message, name: str) -> bool:
    field = message.DESCRIPTOR.fields_by_name[name]
    if field.has_presence:
        return message.HasField(name)
    return any(present is field for present, _ in message.ListFields())


def _enum_name(field: Any, value: int) -> str:
    name = field.enum_type.values_by_number[value].name
    prefix = field.enum_type.values[0].name.removesuffix("UNSPECIFIED")
    return name.removeprefix(prefix).lower()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


converters = ProtobufConverterRegistry()
