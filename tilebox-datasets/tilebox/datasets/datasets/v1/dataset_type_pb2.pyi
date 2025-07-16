from tilebox.datasets.datasets.v1 import well_known_types_pb2 as _well_known_types_pb2
from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DatasetKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATASET_KIND_UNSPECIFIED: _ClassVar[DatasetKind]
    DATASET_KIND_TEMPORAL: _ClassVar[DatasetKind]
    DATASET_KIND_SPATIOTEMPORAL: _ClassVar[DatasetKind]
DATASET_KIND_UNSPECIFIED: DatasetKind
DATASET_KIND_TEMPORAL: DatasetKind
DATASET_KIND_SPATIOTEMPORAL: DatasetKind

class Field(_message.Message):
    __slots__ = ("descriptor", "annotation", "queryable")
    DESCRIPTOR_FIELD_NUMBER: _ClassVar[int]
    ANNOTATION_FIELD_NUMBER: _ClassVar[int]
    QUERYABLE_FIELD_NUMBER: _ClassVar[int]
    descriptor: _descriptor_pb2.FieldDescriptorProto
    annotation: FieldAnnotation
    queryable: bool
    def __init__(self, descriptor: _Optional[_Union[_descriptor_pb2.FieldDescriptorProto, _Mapping]] = ..., annotation: _Optional[_Union[FieldAnnotation, _Mapping]] = ..., queryable: bool = ...) -> None: ...

class FieldAnnotation(_message.Message):
    __slots__ = ("description", "example_value")
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    EXAMPLE_VALUE_FIELD_NUMBER: _ClassVar[int]
    description: str
    example_value: str
    def __init__(self, description: _Optional[str] = ..., example_value: _Optional[str] = ...) -> None: ...

class DatasetType(_message.Message):
    __slots__ = ("kind", "fields")
    KIND_FIELD_NUMBER: _ClassVar[int]
    FIELDS_FIELD_NUMBER: _ClassVar[int]
    kind: DatasetKind
    fields: _containers.RepeatedCompositeFieldContainer[Field]
    def __init__(self, kind: _Optional[_Union[DatasetKind, str]] = ..., fields: _Optional[_Iterable[_Union[Field, _Mapping]]] = ...) -> None: ...

class AnnotatedType(_message.Message):
    __slots__ = ("descriptor_set", "type_url", "field_annotations", "kind")
    DESCRIPTOR_SET_FIELD_NUMBER: _ClassVar[int]
    TYPE_URL_FIELD_NUMBER: _ClassVar[int]
    FIELD_ANNOTATIONS_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    descriptor_set: _descriptor_pb2.FileDescriptorSet
    type_url: str
    field_annotations: _containers.RepeatedCompositeFieldContainer[FieldAnnotation]
    kind: DatasetKind
    def __init__(self, descriptor_set: _Optional[_Union[_descriptor_pb2.FileDescriptorSet, _Mapping]] = ..., type_url: _Optional[str] = ..., field_annotations: _Optional[_Iterable[_Union[FieldAnnotation, _Mapping]]] = ..., kind: _Optional[_Union[DatasetKind, str]] = ...) -> None: ...

class TemporalDatapoint(_message.Message):
    __slots__ = ("time", "id", "ingestion_time")
    TIME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    INGESTION_TIME_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    id: _id_pb2.ID
    ingestion_time: _timestamp_pb2.Timestamp
    def __init__(self, time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., ingestion_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SpatioTemporalDatapoint(_message.Message):
    __slots__ = ("time", "id", "ingestion_time", "geometry")
    TIME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    INGESTION_TIME_FIELD_NUMBER: _ClassVar[int]
    GEOMETRY_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    id: _id_pb2.ID
    ingestion_time: _timestamp_pb2.Timestamp
    geometry: _well_known_types_pb2.Geometry
    def __init__(self, time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., ingestion_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., geometry: _Optional[_Union[_well_known_types_pb2.Geometry, _Mapping]] = ...) -> None: ...
