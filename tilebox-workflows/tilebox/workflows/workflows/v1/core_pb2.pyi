from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class JobState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    JOB_STATE_UNSPECIFIED: _ClassVar[JobState]
    JOB_STATE_QUEUED: _ClassVar[JobState]
    JOB_STATE_STARTED: _ClassVar[JobState]
    JOB_STATE_COMPLETED: _ClassVar[JobState]

class TaskState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TASK_STATE_UNSPECIFIED: _ClassVar[TaskState]
    TASK_STATE_QUEUED: _ClassVar[TaskState]
    TASK_STATE_RUNNING: _ClassVar[TaskState]
    TASK_STATE_COMPUTED: _ClassVar[TaskState]
    TASK_STATE_FAILED: _ClassVar[TaskState]
    TASK_STATE_CANCELLED: _ClassVar[TaskState]
JOB_STATE_UNSPECIFIED: JobState
JOB_STATE_QUEUED: JobState
JOB_STATE_STARTED: JobState
JOB_STATE_COMPLETED: JobState
TASK_STATE_UNSPECIFIED: TaskState
TASK_STATE_QUEUED: TaskState
TASK_STATE_RUNNING: TaskState
TASK_STATE_COMPUTED: TaskState
TASK_STATE_FAILED: TaskState
TASK_STATE_CANCELLED: TaskState

class Cluster(_message.Message):
    __slots__ = ("slug", "display_name", "deletable")
    SLUG_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DELETABLE_FIELD_NUMBER: _ClassVar[int]
    slug: str
    display_name: str
    deletable: bool
    def __init__(self, slug: _Optional[str] = ..., display_name: _Optional[str] = ..., deletable: bool = ...) -> None: ...

class Job(_message.Message):
    __slots__ = ("id", "name", "trace_parent", "canceled", "state", "submitted_at", "started_at", "task_summaries", "automation_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    CANCELED_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_AT_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    TASK_SUMMARIES_FIELD_NUMBER: _ClassVar[int]
    AUTOMATION_ID_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    name: str
    trace_parent: str
    canceled: bool
    state: JobState
    submitted_at: _timestamp_pb2.Timestamp
    started_at: _timestamp_pb2.Timestamp
    task_summaries: _containers.RepeatedCompositeFieldContainer[TaskSummary]
    automation_id: _id_pb2.ID
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ..., trace_parent: _Optional[str] = ..., canceled: bool = ..., state: _Optional[_Union[JobState, str]] = ..., submitted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., task_summaries: _Optional[_Iterable[_Union[TaskSummary, _Mapping]]] = ..., automation_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class TaskSummary(_message.Message):
    __slots__ = ("id", "display", "state", "parent_id", "started_at", "stopped_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    STOPPED_AT_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    display: str
    state: TaskState
    parent_id: _id_pb2.ID
    started_at: _timestamp_pb2.Timestamp
    stopped_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., display: _Optional[str] = ..., state: _Optional[_Union[TaskState, str]] = ..., parent_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., stopped_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

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
    id: _id_pb2.ID
    identifier: TaskIdentifier
    state: TaskState
    input: bytes
    display: str
    job: Job
    parent_id: _id_pb2.ID
    depends_on: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    lease: TaskLease
    retry_count: int
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., identifier: _Optional[_Union[TaskIdentifier, _Mapping]] = ..., state: _Optional[_Union[TaskState, str]] = ..., input: _Optional[bytes] = ..., display: _Optional[str] = ..., job: _Optional[_Union[Job, _Mapping]] = ..., parent_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., depends_on: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ..., lease: _Optional[_Union[TaskLease, _Mapping]] = ..., retry_count: _Optional[int] = ...) -> None: ...

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

class TaskLease(_message.Message):
    __slots__ = ("lease", "recommended_wait_until_next_extension")
    LEASE_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_WAIT_UNTIL_NEXT_EXTENSION_FIELD_NUMBER: _ClassVar[int]
    lease: _duration_pb2.Duration
    recommended_wait_until_next_extension: _duration_pb2.Duration
    def __init__(self, lease: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., recommended_wait_until_next_extension: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...
