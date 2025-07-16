from tilebox.datasets.datasets.v1 import dataset_type_pb2 as _dataset_type_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DatasetPermission(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATASET_PERMISSION_UNSPECIFIED: _ClassVar[DatasetPermission]
    DATASET_PERMISSION_ACCESS_DATA: _ClassVar[DatasetPermission]
    DATASET_PERMISSION_WRITE_DATA: _ClassVar[DatasetPermission]
    DATASET_PERMISSION_EDIT: _ClassVar[DatasetPermission]

class Visibility(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VISIBILITY_UNSPECIFIED: _ClassVar[Visibility]
    VISIBILITY_PRIVATE: _ClassVar[Visibility]
    VISIBILITY_SHARED_WITH_ME: _ClassVar[Visibility]
    VISIBILITY_PUBLIC: _ClassVar[Visibility]
DATASET_PERMISSION_UNSPECIFIED: DatasetPermission
DATASET_PERMISSION_ACCESS_DATA: DatasetPermission
DATASET_PERMISSION_WRITE_DATA: DatasetPermission
DATASET_PERMISSION_EDIT: DatasetPermission
VISIBILITY_UNSPECIFIED: Visibility
VISIBILITY_PRIVATE: Visibility
VISIBILITY_SHARED_WITH_ME: Visibility
VISIBILITY_PUBLIC: Visibility

class LegacyPagination(_message.Message):
    __slots__ = ("limit", "starting_after")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    STARTING_AFTER_FIELD_NUMBER: _ClassVar[int]
    limit: int
    starting_after: str
    def __init__(self, limit: _Optional[int] = ..., starting_after: _Optional[str] = ...) -> None: ...

class Any(_message.Message):
    __slots__ = ("type_url", "value")
    TYPE_URL_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    type_url: str
    value: bytes
    def __init__(self, type_url: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...

class RepeatedAny(_message.Message):
    __slots__ = ("type_url", "value")
    TYPE_URL_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    type_url: str
    value: _containers.RepeatedScalarFieldContainer[bytes]
    def __init__(self, type_url: _Optional[str] = ..., value: _Optional[_Iterable[bytes]] = ...) -> None: ...

class DatapointMetadata(_message.Message):
    __slots__ = ("event_time", "ingestion_time", "id")
    EVENT_TIME_FIELD_NUMBER: _ClassVar[int]
    INGESTION_TIME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    event_time: _timestamp_pb2.Timestamp
    ingestion_time: _timestamp_pb2.Timestamp
    id: str
    def __init__(self, event_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., ingestion_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., id: _Optional[str] = ...) -> None: ...

class Datapoints(_message.Message):
    __slots__ = ("meta", "data")
    META_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    meta: _containers.RepeatedCompositeFieldContainer[DatapointMetadata]
    data: RepeatedAny
    def __init__(self, meta: _Optional[_Iterable[_Union[DatapointMetadata, _Mapping]]] = ..., data: _Optional[_Union[RepeatedAny, _Mapping]] = ...) -> None: ...

class DatapointPage(_message.Message):
    __slots__ = ("meta", "data", "next_page")
    META_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    meta: _containers.RepeatedCompositeFieldContainer[DatapointMetadata]
    data: RepeatedAny
    next_page: LegacyPagination
    def __init__(self, meta: _Optional[_Iterable[_Union[DatapointMetadata, _Mapping]]] = ..., data: _Optional[_Union[RepeatedAny, _Mapping]] = ..., next_page: _Optional[_Union[LegacyPagination, _Mapping]] = ...) -> None: ...

class Datapoint(_message.Message):
    __slots__ = ("meta", "data")
    META_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    meta: DatapointMetadata
    data: Any
    def __init__(self, meta: _Optional[_Union[DatapointMetadata, _Mapping]] = ..., data: _Optional[_Union[Any, _Mapping]] = ...) -> None: ...

class Collection(_message.Message):
    __slots__ = ("legacy_id", "name", "id")
    LEGACY_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    legacy_id: str
    name: str
    id: _id_pb2.ID
    def __init__(self, legacy_id: _Optional[str] = ..., name: _Optional[str] = ..., id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class CollectionInfo(_message.Message):
    __slots__ = ("collection", "availability", "count")
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    collection: Collection
    availability: _query_pb2.TimeInterval
    count: int
    def __init__(self, collection: _Optional[_Union[Collection, _Mapping]] = ..., availability: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., count: _Optional[int] = ...) -> None: ...

class CollectionInfos(_message.Message):
    __slots__ = ("data",)
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: _containers.RepeatedCompositeFieldContainer[CollectionInfo]
    def __init__(self, data: _Optional[_Iterable[_Union[CollectionInfo, _Mapping]]] = ...) -> None: ...

class Dataset(_message.Message):
    __slots__ = ("id", "group_id", "type", "code_name", "name", "summary", "icon", "description", "permissions", "visibility", "slug", "type_editable")
    ID_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CODE_NAME_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    VISIBILITY_FIELD_NUMBER: _ClassVar[int]
    SLUG_FIELD_NUMBER: _ClassVar[int]
    TYPE_EDITABLE_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    group_id: _id_pb2.ID
    type: _dataset_type_pb2.AnnotatedType
    code_name: str
    name: str
    summary: str
    icon: str
    description: str
    permissions: _containers.RepeatedScalarFieldContainer[DatasetPermission]
    visibility: Visibility
    slug: str
    type_editable: bool
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., group_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., type: _Optional[_Union[_dataset_type_pb2.AnnotatedType, _Mapping]] = ..., code_name: _Optional[str] = ..., name: _Optional[str] = ..., summary: _Optional[str] = ..., icon: _Optional[str] = ..., description: _Optional[str] = ..., permissions: _Optional[_Iterable[_Union[DatasetPermission, str]]] = ..., visibility: _Optional[_Union[Visibility, str]] = ..., slug: _Optional[str] = ..., type_editable: bool = ...) -> None: ...

class DatasetGroup(_message.Message):
    __slots__ = ("id", "parent_id", "code_name", "name", "icon")
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_NAME_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    parent_id: _id_pb2.ID
    code_name: str
    name: str
    icon: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., parent_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., code_name: _Optional[str] = ..., name: _Optional[str] = ..., icon: _Optional[str] = ...) -> None: ...
