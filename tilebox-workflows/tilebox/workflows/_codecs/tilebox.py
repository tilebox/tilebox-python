from datetime import datetime
from typing import Any

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message

from tilebox.workflows._codec import Codec, CodecRegistry


def _protobuf_codec(python_type: type, message_type: type[Message]) -> Codec:
    def encode(value: Any) -> dict[str, Any]:
        return MessageToDict(value.to_message(), preserving_proto_field_name=True)

    def decode(value: dict[str, Any]) -> Any:
        return python_type.from_message(ParseDict(value, message_type()))  # ty: ignore[unresolved-attribute]

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
    return time_interval_type.from_message(ParseDict(value, message_type()))  # ty: ignore[unresolved-attribute]


def register(registry: CodecRegistry, _: type) -> None:
    from tilebox.datasets.data.data_access import SpatialFilter  # noqa: PLC0415
    from tilebox.datasets.datasets.v1.data_access_pb2 import SpatialFilter as SpatialFilterMessage  # noqa: PLC0415
    from tilebox.datasets.query.id_interval import IDInterval  # noqa: PLC0415
    from tilebox.datasets.query.time_interval import TimeInterval  # noqa: PLC0415
    from tilebox.datasets.tilebox.v1.query_pb2 import IDInterval as IDIntervalMessage  # noqa: PLC0415
    from tilebox.datasets.tilebox.v1.query_pb2 import TimeInterval as TimeIntervalMessage  # noqa: PLC0415

    registry.register(
        Codec(
            TimeInterval,
            lambda value: MessageToDict(value.to_message(), preserving_proto_field_name=True),
            lambda value: _decode_time_interval(TimeInterval, TimeIntervalMessage, value),
            overrides_native=True,
        )
    )
    registry.register(_protobuf_codec(IDInterval, IDIntervalMessage))
    registry.register(_protobuf_codec(SpatialFilter, SpatialFilterMessage))
