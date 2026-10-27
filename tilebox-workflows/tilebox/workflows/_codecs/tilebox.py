from datetime import datetime
from typing import Any

import msgspec
from protobuf import Message

from tilebox.workflows._codec import Codec, CodecRegistry


def _protobuf_codec(python_type: type, message_type: type[Message]) -> Codec:
    def encode(value: Any) -> dict[str, Any]:
        return msgspec.json.decode(value.to_message().to_json(use_proto_field_name=True))

    def decode(value: dict[str, Any]) -> Any:
        return python_type.from_message(message_type.from_json(msgspec.json.encode(value)))  # ty: ignore[unresolved-attribute]

    return Codec(python_type, encode, decode, overrides_native=True)


def _decode_time_interval(time_interval_type: type, message_type: type[Message], value: dict[str, Any]) -> Any:
    """Decode both the legacy JSON wire shape and the current protobuf-JSON shape."""
    if "start" in value or "end" in value:
        return time_interval_type(
            start=datetime.fromisoformat(value["start"]),
            end=datetime.fromisoformat(value["end"]),
            start_exclusive=value.get("start_exclusive", False),
            end_inclusive=value.get("end_inclusive", False),
        )
    return time_interval_type.from_message(message_type.from_json(msgspec.json.encode(value)))  # ty: ignore[unresolved-attribute]


def register(registry: CodecRegistry, python_type: type) -> None:
    from _tilebox.proto.tilebox.v1.query_pb import IDInterval as IDIntervalMessage  # noqa: PLC0415
    from _tilebox.proto.tilebox.v1.query_pb import TimeInterval as TimeIntervalMessage  # noqa: PLC0415
    from tilebox.query import IDInterval, TimeInterval  # noqa: PLC0415

    registry.register(
        Codec(
            TimeInterval,
            lambda value: msgspec.json.decode(value.to_message().to_json(use_proto_field_name=True)),
            lambda value: _decode_time_interval(TimeInterval, TimeIntervalMessage, value),
            overrides_native=True,
        )
    )
    registry.register(_protobuf_codec(IDInterval, IDIntervalMessage))
    if any(base.__module__.startswith("tilebox.datasets.") for base in python_type.__mro__):
        from tilebox.datasets.data.data_access import SpatialFilter  # noqa: PLC0415
        from tilebox.datasets.v1.data_access_pb import SpatialFilter as SpatialFilterMessage  # noqa: PLC0415

        registry.register(_protobuf_codec(SpatialFilter, SpatialFilterMessage))
