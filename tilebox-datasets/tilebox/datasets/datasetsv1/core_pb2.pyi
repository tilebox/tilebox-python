from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.datasetsv1 import dataset_type_pb2 as _dataset_type_pb2
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

class ID(_message.Message):
    __slots__ = ("uuid",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    uuid: bytes
    def __init__(self, uuid: _Optional[bytes] = ...) -> None: ...

class TimeInterval(_message.Message):
    __slots__ = ("start_time", "end_time", "start_exclusive", "end_inclusive")
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    START_EXCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    END_INCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    start_exclusive: bool
    end_inclusive: bool
    def __init__(self, start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., start_exclusive: bool = ..., end_inclusive: bool = ...) -> None: ...

class DatapointInterval(_message.Message):
    __slots__ = ("start_id", "end_id", "start_exclusive", "end_inclusive")
    START_ID_FIELD_NUMBER: _ClassVar[int]
    END_ID_FIELD_NUMBER: _ClassVar[int]
    START_EXCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    END_INCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    start_id: str
    end_id: str
    start_exclusive: bool
    end_inclusive: bool
    def __init__(self, start_id: _Optional[str] = ..., end_id: _Optional[str] = ..., start_exclusive: bool = ..., end_inclusive: bool = ...) -> None: ...

class Pagination(_message.Message):
    __slots__ = ("limit", "starting_after")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    STARTING_AFTER_FIELD_NUMBER: _ClassVar[int]
    limit: int
    starting_after: str
    def __init__(self, limit: _Optional[int] = ..., starting_after: _Optional[str] = ...) -> None: ...

class DatapointMetadata(_message.Message):
    __slots__ = ("event_time", "ingestion_time", "id")
    EVENT_TIME_FIELD_NUMBER: _ClassVar[int]
    INGESTION_TIME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    event_time: _timestamp_pb2.Timestamp
    ingestion_time: _timestamp_pb2.Timestamp
    id: str
    def __init__(self, event_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., ingestion_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., id: _Optional[str] = ...) -> None: ...

class Collection(_message.Message):
    __slots__ = ("id", "name")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class CollectionInfo(_message.Message):
    __slots__ = ("collection", "availability", "count")
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    collection: Collection
    availability: TimeInterval
    count: int
    def __init__(self, collection: _Optional[_Union[Collection, _Mapping]] = ..., availability: _Optional[_Union[TimeInterval, _Mapping]] = ..., count: _Optional[int] = ...) -> None: ...

class Collections(_message.Message):
    __slots__ = ("data",)
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: _containers.RepeatedCompositeFieldContainer[CollectionInfo]
    def __init__(self, data: _Optional[_Iterable[_Union[CollectionInfo, _Mapping]]] = ...) -> None: ...

class Dataset(_message.Message):
    __slots__ = ("id", "group_id", "type", "code_name", "name", "summary", "icon", "description", "permissions", "visibility")
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
    id: ID
    group_id: ID
    type: _dataset_type_pb2.AnnotatedType
    code_name: str
    name: str
    summary: str
    icon: str
    description: str
    permissions: _containers.RepeatedScalarFieldContainer[DatasetPermission]
    visibility: Visibility
    def __init__(self, id: _Optional[_Union[ID, _Mapping]] = ..., group_id: _Optional[_Union[ID, _Mapping]] = ..., type: _Optional[_Union[_dataset_type_pb2.AnnotatedType, _Mapping]] = ..., code_name: _Optional[str] = ..., name: _Optional[str] = ..., summary: _Optional[str] = ..., icon: _Optional[str] = ..., description: _Optional[str] = ..., permissions: _Optional[_Iterable[_Union[DatasetPermission, str]]] = ..., visibility: _Optional[_Union[Visibility, str]] = ...) -> None: ...

class DatasetGroup(_message.Message):
    __slots__ = ("id", "parent_id", "code_name", "name", "icon")
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_NAME_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    id: ID
    parent_id: ID
    code_name: str
    name: str
    icon: str
    def __init__(self, id: _Optional[_Union[ID, _Mapping]] = ..., parent_id: _Optional[_Union[ID, _Mapping]] = ..., code_name: _Optional[str] = ..., name: _Optional[str] = ..., icon: _Optional[str] = ...) -> None: ...

class CreateCollectionRequest(_message.Message):
    __slots__ = ("dataset_id", "name")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    dataset_id: ID
    name: str
    def __init__(self, dataset_id: _Optional[_Union[ID, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class GetCollectionsRequest(_message.Message):
    __slots__ = ("dataset_id", "with_availability", "with_count")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    WITH_AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    WITH_COUNT_FIELD_NUMBER: _ClassVar[int]
    dataset_id: ID
    with_availability: bool
    with_count: bool
    def __init__(self, dataset_id: _Optional[_Union[ID, _Mapping]] = ..., with_availability: bool = ..., with_count: bool = ...) -> None: ...

class GetCollectionByNameRequest(_message.Message):
    __slots__ = ("collection_name", "with_availability", "with_count", "dataset_id")
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    WITH_AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    WITH_COUNT_FIELD_NUMBER: _ClassVar[int]
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    with_availability: bool
    with_count: bool
    dataset_id: ID
    def __init__(self, collection_name: _Optional[str] = ..., with_availability: bool = ..., with_count: bool = ..., dataset_id: _Optional[_Union[ID, _Mapping]] = ...) -> None: ...

class GetDatasetForIntervalRequest(_message.Message):
    __slots__ = ("collection_id", "time_interval", "datapoint_interval", "page", "skip_data", "skip_meta")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    SKIP_META_FIELD_NUMBER: _ClassVar[int]
    collection_id: str
    time_interval: TimeInterval
    datapoint_interval: DatapointInterval
    page: Pagination
    skip_data: bool
    skip_meta: bool
    def __init__(self, collection_id: _Optional[str] = ..., time_interval: _Optional[_Union[TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[DatapointInterval, _Mapping]] = ..., page: _Optional[_Union[Pagination, _Mapping]] = ..., skip_data: bool = ..., skip_meta: bool = ...) -> None: ...

class GetDatapointByIdRequest(_message.Message):
    __slots__ = ("collection_id", "id", "skip_data")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_id: str
    id: str
    skip_data: bool
    def __init__(self, collection_id: _Optional[str] = ..., id: _Optional[str] = ..., skip_data: bool = ...) -> None: ...

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
