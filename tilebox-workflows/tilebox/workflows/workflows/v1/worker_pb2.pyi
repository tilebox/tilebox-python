from tilebox.datasets.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from tilebox.workflows.workflows.v1 import task_pb2 as _task_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HandshakeRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HandshakeResponse(_message.Message):
    __slots__ = ("task_identifiers",)
    TASK_IDENTIFIERS_FIELD_NUMBER: _ClassVar[int]
    task_identifiers: _core_pb2.TaskIdentifiers
    def __init__(self, task_identifiers: _Optional[_Union[_core_pb2.TaskIdentifiers, _Mapping]] = ...) -> None: ...

class ExecuteTaskResponse(_message.Message):
    __slots__ = ("computed_task", "failed_task")
    COMPUTED_TASK_FIELD_NUMBER: _ClassVar[int]
    FAILED_TASK_FIELD_NUMBER: _ClassVar[int]
    computed_task: _task_pb2.ComputedTask
    failed_task: _task_pb2.TaskFailedRequest
    def __init__(self, computed_task: _Optional[_Union[_task_pb2.ComputedTask, _Mapping]] = ..., failed_task: _Optional[_Union[_task_pb2.TaskFailedRequest, _Mapping]] = ...) -> None: ...
