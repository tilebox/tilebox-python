from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import message as _message
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers

from tilebox.datasets.datasetsv1 import well_known_types_pb2 as _well_known_types_pb2

DESCRIPTOR_PROTO: bytes
DESCRIPTOR: _descriptor.FileDescriptor

class ExampleDatapoint(_message.Message):
    __slots__ = (
        "some_bytes",
        "some_duration",
        "some_enum",
        "some_geometry",
        "some_id",
        "some_int",
        "some_latlon",
        "some_latlon_alt",
        "some_quaternion",
        "some_repeated_int",
        "some_repeated_string",
        "some_string",
        "some_time",
        "some_vec3",
    )
    SOME_STRING_FIELD_NUMBER: _ClassVar[int]
    SOME_INT_FIELD_NUMBER: _ClassVar[int]
    SOME_TIME_FIELD_NUMBER: _ClassVar[int]
    SOME_DURATION_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_STRING_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_INT_FIELD_NUMBER: _ClassVar[int]
    SOME_BYTES_FIELD_NUMBER: _ClassVar[int]
    SOME_ID_FIELD_NUMBER: _ClassVar[int]
    SOME_VEC3_FIELD_NUMBER: _ClassVar[int]
    SOME_QUATERNION_FIELD_NUMBER: _ClassVar[int]
    SOME_LATLON_FIELD_NUMBER: _ClassVar[int]
    SOME_LATLON_ALT_FIELD_NUMBER: _ClassVar[int]
    SOME_GEOMETRY_FIELD_NUMBER: _ClassVar[int]
    SOME_ENUM_FIELD_NUMBER: _ClassVar[int]
    some_string: str
    some_int: int
    some_time: _timestamp_pb2.Timestamp
    some_duration: _duration_pb2.Duration
    some_repeated_string: _containers.RepeatedScalarFieldContainer[str]
    some_repeated_int: _containers.RepeatedScalarFieldContainer[int]
    some_bytes: bytes
    some_id: _well_known_types_pb2.UUID
    some_vec3: _well_known_types_pb2.Vec3
    some_quaternion: _well_known_types_pb2.Quaternion
    some_latlon: _well_known_types_pb2.LatLon
    some_latlon_alt: _well_known_types_pb2.LatLonAlt
    some_geometry: _well_known_types_pb2.GeobufData
    some_enum: _well_known_types_pb2.ProcessingLevel
    def __init__(
        self,
        some_string: str | None = ...,
        some_int: int | None = ...,
        some_time: _timestamp_pb2.Timestamp | _Mapping | None = ...,
        some_duration: _duration_pb2.Duration | _Mapping | None = ...,
        some_repeated_string: _Iterable[str] | None = ...,
        some_repeated_int: _Iterable[int] | None = ...,
        some_bytes: bytes | None = ...,
        some_id: _well_known_types_pb2.UUID | _Mapping | None = ...,
        some_vec3: _well_known_types_pb2.Vec3 | _Mapping | None = ...,
        some_quaternion: _well_known_types_pb2.Quaternion | _Mapping | None = ...,
        some_latlon: _well_known_types_pb2.LatLon | _Mapping | None = ...,
        some_latlon_alt: _well_known_types_pb2.LatLonAlt | _Mapping | None = ...,
        some_geometry: _well_known_types_pb2.GeobufData | _Mapping | None = ...,
        some_enum: _well_known_types_pb2.ProcessingLevel | str | None = ...,
    ) -> None: ...
