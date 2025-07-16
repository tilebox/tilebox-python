from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
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

class IDInterval(_message.Message):
    __slots__ = ("start_id", "end_id", "start_exclusive", "end_inclusive")
    START_ID_FIELD_NUMBER: _ClassVar[int]
    END_ID_FIELD_NUMBER: _ClassVar[int]
    START_EXCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    END_INCLUSIVE_FIELD_NUMBER: _ClassVar[int]
    start_id: _id_pb2.ID
    end_id: _id_pb2.ID
    start_exclusive: bool
    end_inclusive: bool
    def __init__(self, start_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., end_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., start_exclusive: bool = ..., end_inclusive: bool = ...) -> None: ...

class Pagination(_message.Message):
    __slots__ = ("limit", "starting_after")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    STARTING_AFTER_FIELD_NUMBER: _ClassVar[int]
    limit: int
    starting_after: _id_pb2.ID
    def __init__(self, limit: _Optional[int] = ..., starting_after: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...
