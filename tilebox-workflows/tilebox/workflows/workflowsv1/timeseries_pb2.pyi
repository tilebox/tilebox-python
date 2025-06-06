from tilebox.workflows.workflowsv1 import core_pb2 as _core_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

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
    __slots__ = ("start", "end")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    start: _core_pb2.UUID
    end: _core_pb2.UUID
    def __init__(self, start: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., end: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ...) -> None: ...

class TimeseriesDatasetChunk(_message.Message):
    __slots__ = ("dataset_id", "collection_id", "time_interval", "datapoint_interval", "branch_factor", "chunk_size", "datapoints_per_365_days")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    BRANCH_FACTOR_FIELD_NUMBER: _ClassVar[int]
    CHUNK_SIZE_FIELD_NUMBER: _ClassVar[int]
    DATAPOINTS_PER_365_DAYS_FIELD_NUMBER: _ClassVar[int]
    dataset_id: _core_pb2.UUID
    collection_id: _core_pb2.UUID
    time_interval: TimeInterval
    datapoint_interval: DatapointInterval
    branch_factor: int
    chunk_size: int
    datapoints_per_365_days: int
    def __init__(self, dataset_id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., collection_id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., time_interval: _Optional[_Union[TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[DatapointInterval, _Mapping]] = ..., branch_factor: _Optional[int] = ..., chunk_size: _Optional[int] = ..., datapoints_per_365_days: _Optional[int] = ...) -> None: ...

class TimeChunk(_message.Message):
    __slots__ = ("time_interval", "chunk_size")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    CHUNK_SIZE_FIELD_NUMBER: _ClassVar[int]
    time_interval: TimeInterval
    chunk_size: _duration_pb2.Duration
    def __init__(self, time_interval: _Optional[_Union[TimeInterval, _Mapping]] = ..., chunk_size: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...
