from tilebox.workflows.workflowsv1 import core_pb2 as _core_pb2
from tilebox.workflows.workflowsv1 import diagram_pb2 as _diagram_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SubmitJobRequest(_message.Message):
    __slots__ = ("tasks", "job_name", "trace_parent")
    TASKS_FIELD_NUMBER: _ClassVar[int]
    JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskSubmission]
    job_name: str
    trace_parent: str
    def __init__(self, tasks: _Optional[_Iterable[_Union[_core_pb2.TaskSubmission, _Mapping]]] = ..., job_name: _Optional[str] = ..., trace_parent: _Optional[str] = ...) -> None: ...

class GetJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _core_pb2.UUID
    def __init__(self, job_id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ...) -> None: ...

class RetryJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _core_pb2.UUID
    def __init__(self, job_id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ...) -> None: ...

class RetryJobResponse(_message.Message):
    __slots__ = ("num_tasks_rescheduled",)
    NUM_TASKS_RESCHEDULED_FIELD_NUMBER: _ClassVar[int]
    num_tasks_rescheduled: int
    def __init__(self, num_tasks_rescheduled: _Optional[int] = ...) -> None: ...

class CancelJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _core_pb2.UUID
    def __init__(self, job_id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ...) -> None: ...

class CancelJobResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class VisualizeJobRequest(_message.Message):
    __slots__ = ("job_id", "render_options")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    RENDER_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    job_id: _core_pb2.UUID
    render_options: _diagram_pb2.RenderOptions
    def __init__(self, job_id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., render_options: _Optional[_Union[_diagram_pb2.RenderOptions, _Mapping]] = ...) -> None: ...
