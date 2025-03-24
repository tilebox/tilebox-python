from tilebox.datasets.datasetsv1 import core_pb2 as _core_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetDatasetForIntervalRequest(_message.Message):
    __slots__ = ("collection_id", "time_interval", "datapoint_interval", "page", "skip_data", "skip_meta")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    SKIP_META_FIELD_NUMBER: _ClassVar[int]
    collection_id: str
    time_interval: _core_pb2.TimeInterval
    datapoint_interval: _core_pb2.DatapointInterval
    page: _core_pb2.LegacyPagination
    skip_data: bool
    skip_meta: bool
    def __init__(self, collection_id: _Optional[str] = ..., time_interval: _Optional[_Union[_core_pb2.TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[_core_pb2.DatapointInterval, _Mapping]] = ..., page: _Optional[_Union[_core_pb2.LegacyPagination, _Mapping]] = ..., skip_data: bool = ..., skip_meta: bool = ...) -> None: ...

class GetDatapointByIdRequest(_message.Message):
    __slots__ = ("collection_id", "id", "skip_data")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_id: str
    id: str
    skip_data: bool
    def __init__(self, collection_id: _Optional[str] = ..., id: _Optional[str] = ..., skip_data: bool = ...) -> None: ...

class QueryByIDRequest(_message.Message):
    __slots__ = ("collection_ids", "id", "skip_data")
    COLLECTION_IDS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_ids: _containers.RepeatedCompositeFieldContainer[_core_pb2.ID]
    id: _core_pb2.ID
    skip_data: bool
    def __init__(self, collection_ids: _Optional[_Iterable[_Union[_core_pb2.ID, _Mapping]]] = ..., id: _Optional[_Union[_core_pb2.ID, _Mapping]] = ..., skip_data: bool = ...) -> None: ...

class QueryFilters(_message.Message):
    __slots__ = ("time_interval", "datapoint_interval")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    time_interval: _core_pb2.TimeInterval
    datapoint_interval: _core_pb2.DatapointInterval
    def __init__(self, time_interval: _Optional[_Union[_core_pb2.TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[_core_pb2.DatapointInterval, _Mapping]] = ...) -> None: ...

class QueryRequest(_message.Message):
    __slots__ = ("collection_ids", "filters", "page", "skip_data")
    COLLECTION_IDS_FIELD_NUMBER: _ClassVar[int]
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_ids: _containers.RepeatedCompositeFieldContainer[_core_pb2.ID]
    filters: QueryFilters
    page: _core_pb2.Pagination
    skip_data: bool
    def __init__(self, collection_ids: _Optional[_Iterable[_Union[_core_pb2.ID, _Mapping]]] = ..., filters: _Optional[_Union[QueryFilters, _Mapping]] = ..., page: _Optional[_Union[_core_pb2.Pagination, _Mapping]] = ..., skip_data: bool = ...) -> None: ...

class QueryResultPage(_message.Message):
    __slots__ = ("data", "next_page")
    DATA_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    data: _core_pb2.RepeatedAny
    next_page: _core_pb2.Pagination
    def __init__(self, data: _Optional[_Union[_core_pb2.RepeatedAny, _Mapping]] = ..., next_page: _Optional[_Union[_core_pb2.Pagination, _Mapping]] = ...) -> None: ...
