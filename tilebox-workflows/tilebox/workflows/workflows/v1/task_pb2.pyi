from google.protobuf import duration_pb2 as _duration_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class NextTaskRequest(_message.Message):
    __slots__ = ("computed_task", "next_task_to_run")
    COMPUTED_TASK_FIELD_NUMBER: _ClassVar[int]
    NEXT_TASK_TO_RUN_FIELD_NUMBER: _ClassVar[int]
    computed_task: ComputedTask
    next_task_to_run: NextTaskToRun
    def __init__(self, computed_task: _Optional[_Union[ComputedTask, _Mapping]] = ..., next_task_to_run: _Optional[_Union[NextTaskToRun, _Mapping]] = ...) -> None: ...

class NextTaskToRun(_message.Message):
    __slots__ = ("cluster_slug", "identifiers")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIERS_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    identifiers: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskIdentifier]
    def __init__(self, cluster_slug: _Optional[str] = ..., identifiers: _Optional[_Iterable[_Union[_core_pb2.TaskIdentifier, _Mapping]]] = ...) -> None: ...

class ComputedTask(_message.Message):
    __slots__ = ("id", "display", "sub_tasks")
    ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    SUB_TASKS_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    display: str
    sub_tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskSubmission]
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., display: _Optional[str] = ..., sub_tasks: _Optional[_Iterable[_Union[_core_pb2.TaskSubmission, _Mapping]]] = ...) -> None: ...

class NextTaskResponse(_message.Message):
    __slots__ = ("next_task",)
    NEXT_TASK_FIELD_NUMBER: _ClassVar[int]
    next_task: _core_pb2.Task
    def __init__(self, next_task: _Optional[_Union[_core_pb2.Task, _Mapping]] = ...) -> None: ...

class TaskFailedRequest(_message.Message):
    __slots__ = ("task_id", "display", "cancel_job")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    CANCEL_JOB_FIELD_NUMBER: _ClassVar[int]
    task_id: _id_pb2.ID
    display: str
    cancel_job: bool
    def __init__(self, task_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., display: _Optional[str] = ..., cancel_job: bool = ...) -> None: ...

class TaskStateResponse(_message.Message):
    __slots__ = ("state",)
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: _core_pb2.TaskState
    def __init__(self, state: _Optional[_Union[_core_pb2.TaskState, str]] = ...) -> None: ...

class TaskLeaseRequest(_message.Message):
    __slots__ = ("task_id", "requested_lease")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_LEASE_FIELD_NUMBER: _ClassVar[int]
    task_id: _id_pb2.ID
    requested_lease: _duration_pb2.Duration
    def __init__(self, task_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., requested_lease: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...
