from tilebox.datasets.datasetsv1 import core_pb2 as _core_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

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
    page: _core_pb2.Pagination
    skip_data: bool
    skip_meta: bool
    def __init__(self, collection_id: _Optional[str] = ..., time_interval: _Optional[_Union[_core_pb2.TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[_core_pb2.DatapointInterval, _Mapping]] = ..., page: _Optional[_Union[_core_pb2.Pagination, _Mapping]] = ..., skip_data: bool = ..., skip_meta: bool = ...) -> None: ...

class GetDatapointByIdRequest(_message.Message):
    __slots__ = ("collection_id", "id", "skip_data")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_id: str
    id: str
    skip_data: bool
    def __init__(self, collection_id: _Optional[str] = ..., id: _Optional[str] = ..., skip_data: bool = ...) -> None: ...
