from google.protobuf import duration_pb2 as _duration_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TimeseriesDatasetChunk(_message.Message):
    __slots__ = ("dataset_id", "collection_id", "time_interval", "datapoint_interval", "branch_factor", "chunk_size", "datapoints_per_365_days")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    BRANCH_FACTOR_FIELD_NUMBER: _ClassVar[int]
    CHUNK_SIZE_FIELD_NUMBER: _ClassVar[int]
    DATAPOINTS_PER_365_DAYS_FIELD_NUMBER: _ClassVar[int]
    dataset_id: _id_pb2.ID
    collection_id: _id_pb2.ID
    time_interval: _query_pb2.TimeInterval
    datapoint_interval: _query_pb2.IDInterval
    branch_factor: int
    chunk_size: int
    datapoints_per_365_days: int
    def __init__(self, dataset_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., collection_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[_query_pb2.IDInterval, _Mapping]] = ..., branch_factor: _Optional[int] = ..., chunk_size: _Optional[int] = ..., datapoints_per_365_days: _Optional[int] = ...) -> None: ...

class TimeChunk(_message.Message):
    __slots__ = ("time_interval", "chunk_size")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    CHUNK_SIZE_FIELD_NUMBER: _ClassVar[int]
    time_interval: _query_pb2.TimeInterval
    chunk_size: _duration_pb2.Duration
    def __init__(self, time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., chunk_size: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...
