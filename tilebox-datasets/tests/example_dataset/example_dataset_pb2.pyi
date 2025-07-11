from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import message as _message
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers

from tilebox.datasets.datasets.v1 import well_known_types_pb2 as _well_known_types_pb2

DESCRIPTOR_PROTO: bytes
DESCRIPTOR: _descriptor.FileDescriptor

class ExampleDatapoint(_message.Message):
    __slots__ = (
        "geometry",
        "id",
        "ingestion_time",
        "some_bool",
        "some_bytes",
        "some_double",
        "some_duration",
        "some_enum",
        "some_geometry",
        "some_identifier",
        "some_int",
        "some_quaternion",
        "some_repeated_bool",
        "some_repeated_bytes",
        "some_repeated_double",
        "some_repeated_duration",
        "some_repeated_geometry",
        "some_repeated_identifier",
        "some_repeated_int",
        "some_repeated_string",
        "some_repeated_time",
        "some_repeated_vec3",
        "some_string",
        "some_time",
        "some_vec3",
        "time",
    )
    TIME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    INGESTION_TIME_FIELD_NUMBER: _ClassVar[int]
    GEOMETRY_FIELD_NUMBER: _ClassVar[int]
    SOME_STRING_FIELD_NUMBER: _ClassVar[int]
    SOME_INT_FIELD_NUMBER: _ClassVar[int]
    SOME_DOUBLE_FIELD_NUMBER: _ClassVar[int]
    SOME_TIME_FIELD_NUMBER: _ClassVar[int]
    SOME_DURATION_FIELD_NUMBER: _ClassVar[int]
    SOME_BYTES_FIELD_NUMBER: _ClassVar[int]
    SOME_BOOL_FIELD_NUMBER: _ClassVar[int]
    SOME_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    SOME_VEC3_FIELD_NUMBER: _ClassVar[int]
    SOME_QUATERNION_FIELD_NUMBER: _ClassVar[int]
    SOME_GEOMETRY_FIELD_NUMBER: _ClassVar[int]
    SOME_ENUM_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_STRING_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_INT_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_DOUBLE_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_BYTES_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_BOOL_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_TIME_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_DURATION_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_VEC3_FIELD_NUMBER: _ClassVar[int]
    SOME_REPEATED_GEOMETRY_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    id: _well_known_types_pb2.UUID
    ingestion_time: _timestamp_pb2.Timestamp
    geometry: _well_known_types_pb2.Geometry
    some_string: str
    some_int: int
    some_double: float
    some_time: _timestamp_pb2.Timestamp
    some_duration: _duration_pb2.Duration
    some_bytes: bytes
    some_bool: bool
    some_identifier: _well_known_types_pb2.UUID
    some_vec3: _well_known_types_pb2.Vec3
    some_quaternion: _well_known_types_pb2.Quaternion
    some_geometry: _well_known_types_pb2.Geometry
    some_enum: _well_known_types_pb2.ProcessingLevel
    some_repeated_string: _containers.RepeatedScalarFieldContainer[str]
    some_repeated_int: _containers.RepeatedScalarFieldContainer[int]
    some_repeated_double: _containers.RepeatedScalarFieldContainer[float]
    some_repeated_bytes: _containers.RepeatedScalarFieldContainer[bytes]
    some_repeated_bool: _containers.RepeatedScalarFieldContainer[bool]
    some_repeated_time: _containers.RepeatedCompositeFieldContainer[_timestamp_pb2.Timestamp]
    some_repeated_duration: _containers.RepeatedCompositeFieldContainer[_duration_pb2.Duration]
    some_repeated_identifier: _containers.RepeatedCompositeFieldContainer[_well_known_types_pb2.UUID]
    some_repeated_vec3: _containers.RepeatedCompositeFieldContainer[_well_known_types_pb2.Vec3]
    some_repeated_geometry: _containers.RepeatedCompositeFieldContainer[_well_known_types_pb2.Geometry]
    def __init__(
        self,
        time: _timestamp_pb2.Timestamp | _Mapping | None = ...,
        id: _well_known_types_pb2.UUID | _Mapping | None = ...,  # noqa: A002
        ingestion_time: _timestamp_pb2.Timestamp | _Mapping | None = ...,
        geometry: _well_known_types_pb2.Geometry | _Mapping | None = ...,
        some_string: str | None = ...,
        some_int: int | None = ...,
        some_double: float | None = ...,
        some_time: _timestamp_pb2.Timestamp | _Mapping | None = ...,
        some_duration: _duration_pb2.Duration | _Mapping | None = ...,
        some_bytes: bytes | None = ...,
        some_bool: bool = ...,
        some_identifier: _well_known_types_pb2.UUID | _Mapping | None = ...,
        some_vec3: _well_known_types_pb2.Vec3 | _Mapping | None = ...,
        some_quaternion: _well_known_types_pb2.Quaternion | _Mapping | None = ...,
        some_geometry: _well_known_types_pb2.Geometry | _Mapping | None = ...,
        some_enum: _well_known_types_pb2.ProcessingLevel | str | None = ...,
        some_repeated_string: _Iterable[str] | None = ...,
        some_repeated_int: _Iterable[int] | None = ...,
        some_repeated_double: _Iterable[float] | None = ...,
        some_repeated_bytes: _Iterable[bytes] | None = ...,
        some_repeated_bool: _Iterable[bool] | None = ...,
        some_repeated_time: _Iterable[_timestamp_pb2.Timestamp | _Mapping] | None = ...,
        some_repeated_duration: _Iterable[_duration_pb2.Duration | _Mapping] | None = ...,
        some_repeated_identifier: _Iterable[_well_known_types_pb2.UUID | _Mapping] | None = ...,
        some_repeated_vec3: _Iterable[_well_known_types_pb2.Vec3 | _Mapping] | None = ...,
        some_repeated_geometry: _Iterable[_well_known_types_pb2.Geometry | _Mapping] | None = ...,
    ) -> None: ...
