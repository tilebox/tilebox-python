from tilebox.datasets.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LegacyJobState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LEGACY_JOB_STATE_UNSPECIFIED: _ClassVar[LegacyJobState]
    LEGACY_JOB_STATE_QUEUED: _ClassVar[LegacyJobState]
    LEGACY_JOB_STATE_STARTED: _ClassVar[LegacyJobState]
    LEGACY_JOB_STATE_COMPLETED: _ClassVar[LegacyJobState]

class JobState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    JOB_STATE_UNSPECIFIED: _ClassVar[JobState]
    JOB_STATE_SUBMITTED: _ClassVar[JobState]
    JOB_STATE_RUNNING: _ClassVar[JobState]
    JOB_STATE_STARTED: _ClassVar[JobState]
    JOB_STATE_COMPLETED: _ClassVar[JobState]
    JOB_STATE_FAILED: _ClassVar[JobState]
    JOB_STATE_CANCELED: _ClassVar[JobState]

class TaskState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TASK_STATE_UNSPECIFIED: _ClassVar[TaskState]
    TASK_STATE_QUEUED: _ClassVar[TaskState]
    TASK_STATE_RUNNING: _ClassVar[TaskState]
    TASK_STATE_COMPUTED: _ClassVar[TaskState]
    TASK_STATE_FAILED: _ClassVar[TaskState]
LEGACY_JOB_STATE_UNSPECIFIED: LegacyJobState
LEGACY_JOB_STATE_QUEUED: LegacyJobState
LEGACY_JOB_STATE_STARTED: LegacyJobState
LEGACY_JOB_STATE_COMPLETED: LegacyJobState
JOB_STATE_UNSPECIFIED: JobState
JOB_STATE_SUBMITTED: JobState
JOB_STATE_RUNNING: JobState
JOB_STATE_STARTED: JobState
JOB_STATE_COMPLETED: JobState
JOB_STATE_FAILED: JobState
JOB_STATE_CANCELED: JobState
TASK_STATE_UNSPECIFIED: TaskState
TASK_STATE_QUEUED: TaskState
TASK_STATE_RUNNING: TaskState
TASK_STATE_COMPUTED: TaskState
TASK_STATE_FAILED: TaskState

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
    __slots__ = ("id", "name", "trace_parent", "canceled", "legacy_state", "submitted_at", "started_at", "task_summaries", "automation_id", "progress", "state", "execution_stats")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    CANCELED_FIELD_NUMBER: _ClassVar[int]
    LEGACY_STATE_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_AT_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    TASK_SUMMARIES_FIELD_NUMBER: _ClassVar[int]
    AUTOMATION_ID_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_STATS_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    name: str
    trace_parent: str
    canceled: bool
    legacy_state: LegacyJobState
    submitted_at: _timestamp_pb2.Timestamp
    started_at: _timestamp_pb2.Timestamp
    task_summaries: _containers.RepeatedCompositeFieldContainer[TaskSummary]
    automation_id: _id_pb2.ID
    progress: _containers.RepeatedCompositeFieldContainer[Progress]
    state: JobState
    execution_stats: ExecutionStats
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ..., trace_parent: _Optional[str] = ..., canceled: bool = ..., legacy_state: _Optional[_Union[LegacyJobState, str]] = ..., submitted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., task_summaries: _Optional[_Iterable[_Union[TaskSummary, _Mapping]]] = ..., automation_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., progress: _Optional[_Iterable[_Union[Progress, _Mapping]]] = ..., state: _Optional[_Union[JobState, str]] = ..., execution_stats: _Optional[_Union[ExecutionStats, _Mapping]] = ...) -> None: ...

class ExecutionStats(_message.Message):
    __slots__ = ("first_task_started_at", "last_task_stopped_at", "compute_time", "elapsed_time", "parallelism", "total_tasks", "tasks_by_state")
    FIRST_TASK_STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_TASK_STOPPED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_TIME_FIELD_NUMBER: _ClassVar[int]
    ELAPSED_TIME_FIELD_NUMBER: _ClassVar[int]
    PARALLELISM_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TASKS_FIELD_NUMBER: _ClassVar[int]
    TASKS_BY_STATE_FIELD_NUMBER: _ClassVar[int]
    first_task_started_at: _timestamp_pb2.Timestamp
    last_task_stopped_at: _timestamp_pb2.Timestamp
    compute_time: _duration_pb2.Duration
    elapsed_time: _duration_pb2.Duration
    parallelism: float
    total_tasks: int
    tasks_by_state: _containers.RepeatedCompositeFieldContainer[TaskStateCount]
    def __init__(self, first_task_started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., last_task_stopped_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., compute_time: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., elapsed_time: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., parallelism: _Optional[float] = ..., total_tasks: _Optional[int] = ..., tasks_by_state: _Optional[_Iterable[_Union[TaskStateCount, _Mapping]]] = ...) -> None: ...

class TaskStateCount(_message.Message):
    __slots__ = ("state", "count")
    STATE_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    state: TaskState
    count: int
    def __init__(self, state: _Optional[_Union[TaskState, str]] = ..., count: _Optional[int] = ...) -> None: ...

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

class Progress(_message.Message):
    __slots__ = ("label", "total", "done")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    label: str
    total: int
    done: int
    def __init__(self, label: _Optional[str] = ..., total: _Optional[int] = ..., done: _Optional[int] = ...) -> None: ...

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

class SingleTaskSubmission(_message.Message):
    __slots__ = ("cluster_slug", "identifier", "display", "dependencies", "max_retries", "input")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    DEPENDENCIES_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    identifier: TaskIdentifier
    display: str
    dependencies: _containers.RepeatedScalarFieldContainer[int]
    max_retries: int
    input: bytes
    def __init__(self, cluster_slug: _Optional[str] = ..., identifier: _Optional[_Union[TaskIdentifier, _Mapping]] = ..., display: _Optional[str] = ..., dependencies: _Optional[_Iterable[int]] = ..., max_retries: _Optional[int] = ..., input: _Optional[bytes] = ...) -> None: ...

class TaskSubmissions(_message.Message):
    __slots__ = ("task_groups", "cluster_slug_lookup", "identifier_lookup", "display_lookup")
    TASK_GROUPS_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_SLUG_LOOKUP_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_LOOKUP_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_LOOKUP_FIELD_NUMBER: _ClassVar[int]
    task_groups: _containers.RepeatedCompositeFieldContainer[TaskSubmissionGroup]
    cluster_slug_lookup: _containers.RepeatedScalarFieldContainer[str]
    identifier_lookup: _containers.RepeatedCompositeFieldContainer[TaskIdentifier]
    display_lookup: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, task_groups: _Optional[_Iterable[_Union[TaskSubmissionGroup, _Mapping]]] = ..., cluster_slug_lookup: _Optional[_Iterable[str]] = ..., identifier_lookup: _Optional[_Iterable[_Union[TaskIdentifier, _Mapping]]] = ..., display_lookup: _Optional[_Iterable[str]] = ...) -> None: ...

class TaskSubmissionGroup(_message.Message):
    __slots__ = ("dependencies_on_other_groups", "inputs", "identifier_pointers", "cluster_slug_pointers", "display_pointers", "max_retries_values")
    DEPENDENCIES_ON_OTHER_GROUPS_FIELD_NUMBER: _ClassVar[int]
    INPUTS_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_POINTERS_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_SLUG_POINTERS_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_POINTERS_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_VALUES_FIELD_NUMBER: _ClassVar[int]
    dependencies_on_other_groups: _containers.RepeatedScalarFieldContainer[int]
    inputs: _containers.RepeatedScalarFieldContainer[bytes]
    identifier_pointers: _containers.RepeatedScalarFieldContainer[int]
    cluster_slug_pointers: _containers.RepeatedScalarFieldContainer[int]
    display_pointers: _containers.RepeatedScalarFieldContainer[int]
    max_retries_values: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, dependencies_on_other_groups: _Optional[_Iterable[int]] = ..., inputs: _Optional[_Iterable[bytes]] = ..., identifier_pointers: _Optional[_Iterable[int]] = ..., cluster_slug_pointers: _Optional[_Iterable[int]] = ..., display_pointers: _Optional[_Iterable[int]] = ..., max_retries_values: _Optional[_Iterable[int]] = ...) -> None: ...

class TaskLease(_message.Message):
    __slots__ = ("lease", "recommended_wait_until_next_extension")
    LEASE_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_WAIT_UNTIL_NEXT_EXTENSION_FIELD_NUMBER: _ClassVar[int]
    lease: _duration_pb2.Duration
    recommended_wait_until_next_extension: _duration_pb2.Duration
    def __init__(self, lease: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., recommended_wait_until_next_extension: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...
