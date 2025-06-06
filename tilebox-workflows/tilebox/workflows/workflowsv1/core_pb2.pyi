from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TaskState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TASK_STATE_UNSPECIFIED: _ClassVar[TaskState]
    TASK_STATE_QUEUED: _ClassVar[TaskState]
    TASK_STATE_RUNNING: _ClassVar[TaskState]
    TASK_STATE_COMPUTED: _ClassVar[TaskState]
    TASK_STATE_FAILED: _ClassVar[TaskState]
    TASK_STATE_CANCELLED: _ClassVar[TaskState]
TASK_STATE_UNSPECIFIED: TaskState
TASK_STATE_QUEUED: TaskState
TASK_STATE_RUNNING: TaskState
TASK_STATE_COMPUTED: TaskState
TASK_STATE_FAILED: TaskState
TASK_STATE_CANCELLED: TaskState

class Cluster(_message.Message):
    __slots__ = ("slug", "display_name")
    SLUG_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    slug: str
    display_name: str
    def __init__(self, slug: _Optional[str] = ..., display_name: _Optional[str] = ...) -> None: ...

class Job(_message.Message):
    __slots__ = ("id", "name", "trace_parent", "completed")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    id: UUID
    name: str
    trace_parent: str
    completed: bool
    def __init__(self, id: _Optional[_Union[UUID, _Mapping]] = ..., name: _Optional[str] = ..., trace_parent: _Optional[str] = ..., completed: bool = ...) -> None: ...

class Task(_message.Message):
    __slots__ = ("id", "identifier", "state", "input", "display", "job", "parent_id", "depends_on", "lease", "retry_count")
    ID_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    JOB_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    DEPENDS_ON_FIELD_NUMBER: _ClassVar[int]
    LEASE_FIELD_NUMBER: _ClassVar[int]
    RETRY_COUNT_FIELD_NUMBER: _ClassVar[int]
    id: UUID
    identifier: TaskIdentifier
    state: TaskState
    input: bytes
    display: str
    job: Job
    parent_id: UUID
    depends_on: _containers.RepeatedCompositeFieldContainer[UUID]
    lease: TaskLease
    retry_count: int
    def __init__(self, id: _Optional[_Union[UUID, _Mapping]] = ..., identifier: _Optional[_Union[TaskIdentifier, _Mapping]] = ..., state: _Optional[_Union[TaskState, str]] = ..., input: _Optional[bytes] = ..., display: _Optional[str] = ..., job: _Optional[_Union[Job, _Mapping]] = ..., parent_id: _Optional[_Union[UUID, _Mapping]] = ..., depends_on: _Optional[_Iterable[_Union[UUID, _Mapping]]] = ..., lease: _Optional[_Union[TaskLease, _Mapping]] = ..., retry_count: _Optional[int] = ...) -> None: ...

class TaskIdentifier(_message.Message):
    __slots__ = ("name", "version")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: str
    def __init__(self, name: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class Tasks(_message.Message):
    __slots__ = ("tasks",)
    TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[Task]
    def __init__(self, tasks: _Optional[_Iterable[_Union[Task, _Mapping]]] = ...) -> None: ...

class TaskSubmission(_message.Message):
    __slots__ = ("cluster_slug", "identifier", "input", "display", "dependencies", "max_retries")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    DEPENDENCIES_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    identifier: TaskIdentifier
    input: bytes
    display: str
    dependencies: _containers.RepeatedScalarFieldContainer[int]
    max_retries: int
    def __init__(self, cluster_slug: _Optional[str] = ..., identifier: _Optional[_Union[TaskIdentifier, _Mapping]] = ..., input: _Optional[bytes] = ..., display: _Optional[str] = ..., dependencies: _Optional[_Iterable[int]] = ..., max_retries: _Optional[int] = ...) -> None: ...

class UUID(_message.Message):
    __slots__ = ("uuid",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    uuid: bytes
    def __init__(self, uuid: _Optional[bytes] = ...) -> None: ...

class TaskLease(_message.Message):
    __slots__ = ("lease", "recommended_wait_until_next_extension")
    LEASE_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_WAIT_UNTIL_NEXT_EXTENSION_FIELD_NUMBER: _ClassVar[int]
    lease: _duration_pb2.Duration
    recommended_wait_until_next_extension: _duration_pb2.Duration
    def __init__(self, lease: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., recommended_wait_until_next_extension: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...
