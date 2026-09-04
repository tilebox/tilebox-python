from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from tilebox.workflows.workflows.v1 import diagram_pb2 as _diagram_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WorkflowDiagramTheme(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WORKFLOW_DIAGRAM_THEME_UNSPECIFIED: _ClassVar[WorkflowDiagramTheme]
    WORKFLOW_DIAGRAM_THEME_LIGHT: _ClassVar[WorkflowDiagramTheme]
    WORKFLOW_DIAGRAM_THEME_DARK: _ClassVar[WorkflowDiagramTheme]
    WORKFLOW_DIAGRAM_THEME_CONSOLE_LIGHT: _ClassVar[WorkflowDiagramTheme]
    WORKFLOW_DIAGRAM_THEME_CONSOLE_DARK: _ClassVar[WorkflowDiagramTheme]
WORKFLOW_DIAGRAM_THEME_UNSPECIFIED: WorkflowDiagramTheme
WORKFLOW_DIAGRAM_THEME_LIGHT: WorkflowDiagramTheme
WORKFLOW_DIAGRAM_THEME_DARK: WorkflowDiagramTheme
WORKFLOW_DIAGRAM_THEME_CONSOLE_LIGHT: WorkflowDiagramTheme
WORKFLOW_DIAGRAM_THEME_CONSOLE_DARK: WorkflowDiagramTheme

class SubmitJobRequest(_message.Message):
    __slots__ = ("tasks", "job_name", "trace_parent", "automation_id", "legacy_tasks")
    TASKS_FIELD_NUMBER: _ClassVar[int]
    JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    AUTOMATION_ID_FIELD_NUMBER: _ClassVar[int]
    LEGACY_TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _core_pb2.TaskSubmissions
    job_name: str
    trace_parent: str
    automation_id: _id_pb2.ID
    legacy_tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.SingleTaskSubmission]
    def __init__(self, tasks: _Optional[_Union[_core_pb2.TaskSubmissions, _Mapping]] = ..., job_name: _Optional[str] = ..., trace_parent: _Optional[str] = ..., automation_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., legacy_tasks: _Optional[_Iterable[_Union[_core_pb2.SingleTaskSubmission, _Mapping]]] = ...) -> None: ...

class GetJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class TaskSummary(_message.Message):
    __slots__ = ("id", "parent_id", "display", "state", "submitted_at", "started_at", "stopped_at", "input", "retry_count", "max_retries", "has_children", "cluster_slug", "optional")
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_AT_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    STOPPED_AT_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    RETRY_COUNT_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_FIELD_NUMBER: _ClassVar[int]
    HAS_CHILDREN_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    OPTIONAL_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    parent_id: _id_pb2.ID
    display: str
    state: _core_pb2.TaskState
    submitted_at: _timestamp_pb2.Timestamp
    started_at: _timestamp_pb2.Timestamp
    stopped_at: _timestamp_pb2.Timestamp
    input: bytes
    retry_count: int
    max_retries: int
    has_children: bool
    cluster_slug: str
    optional: bool
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., parent_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., display: _Optional[str] = ..., state: _Optional[_Union[_core_pb2.TaskState, str]] = ..., submitted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., stopped_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., input: _Optional[bytes] = ..., retry_count: _Optional[int] = ..., max_retries: _Optional[int] = ..., has_children: bool = ..., cluster_slug: _Optional[str] = ..., optional: bool = ...) -> None: ...

class JobTaskChildrenPrefetch(_message.Message):
    __slots__ = ("limit",)
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    limit: int
    def __init__(self, limit: _Optional[int] = ...) -> None: ...

class ListJobTasksRequest(_message.Message):
    __slots__ = ("job_id", "parent_task_id", "page", "prefetch_children")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PREFETCH_CHILDREN_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    parent_task_id: _id_pb2.ID
    page: _query_pb2.Pagination
    prefetch_children: JobTaskChildrenPrefetch
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., parent_task_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ..., prefetch_children: _Optional[_Union[JobTaskChildrenPrefetch, _Mapping]] = ...) -> None: ...

class JobTaskPage(_message.Message):
    __slots__ = ("parent_task_id", "tasks", "next_page")
    PARENT_TASK_ID_FIELD_NUMBER: _ClassVar[int]
    TASKS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    parent_task_id: _id_pb2.ID
    tasks: _containers.RepeatedCompositeFieldContainer[TaskSummary]
    next_page: _query_pb2.Pagination
    def __init__(self, parent_task_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., tasks: _Optional[_Iterable[_Union[TaskSummary, _Mapping]]] = ..., next_page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...

class ListJobTasksResponse(_message.Message):
    __slots__ = ("page", "prefetched_child_pages")
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PREFETCHED_CHILD_PAGES_FIELD_NUMBER: _ClassVar[int]
    page: JobTaskPage
    prefetched_child_pages: _containers.RepeatedCompositeFieldContainer[JobTaskPage]
    def __init__(self, page: _Optional[_Union[JobTaskPage, _Mapping]] = ..., prefetched_child_pages: _Optional[_Iterable[_Union[JobTaskPage, _Mapping]]] = ...) -> None: ...

class RetryJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class RetryJobResponse(_message.Message):
    __slots__ = ("num_tasks_rescheduled",)
    NUM_TASKS_RESCHEDULED_FIELD_NUMBER: _ClassVar[int]
    num_tasks_rescheduled: int
    def __init__(self, num_tasks_rescheduled: _Optional[int] = ...) -> None: ...

class CancelJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class CancelJobResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class VisualizeJobRequest(_message.Message):
    __slots__ = ("job_id", "render_options", "theme", "include_job_name")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    RENDER_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    THEME_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    render_options: _diagram_pb2.RenderOptions
    theme: WorkflowDiagramTheme
    include_job_name: bool
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., render_options: _Optional[_Union[_diagram_pb2.RenderOptions, _Mapping]] = ..., theme: _Optional[_Union[WorkflowDiagramTheme, str]] = ..., include_job_name: bool = ...) -> None: ...

class QueryFilters(_message.Message):
    __slots__ = ("time_interval", "id_interval", "automation_ids", "states", "name", "task_states", "cluster_slugs")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    ID_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    AUTOMATION_IDS_FIELD_NUMBER: _ClassVar[int]
    STATES_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TASK_STATES_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_SLUGS_FIELD_NUMBER: _ClassVar[int]
    time_interval: _query_pb2.TimeInterval
    id_interval: _query_pb2.IDInterval
    automation_ids: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    states: _containers.RepeatedScalarFieldContainer[_core_pb2.JobState]
    name: str
    task_states: _containers.RepeatedScalarFieldContainer[_core_pb2.TaskState]
    cluster_slugs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., id_interval: _Optional[_Union[_query_pb2.IDInterval, _Mapping]] = ..., automation_ids: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ..., states: _Optional[_Iterable[_Union[_core_pb2.JobState, str]]] = ..., name: _Optional[str] = ..., task_states: _Optional[_Iterable[_Union[_core_pb2.TaskState, str]]] = ..., cluster_slugs: _Optional[_Iterable[str]] = ...) -> None: ...

class QueryJobsRequest(_message.Message):
    __slots__ = ("filters", "page", "sort_direction")
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SORT_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    filters: QueryFilters
    page: _query_pb2.Pagination
    sort_direction: _query_pb2.SortDirection
    def __init__(self, filters: _Optional[_Union[QueryFilters, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ..., sort_direction: _Optional[_Union[_query_pb2.SortDirection, str]] = ...) -> None: ...

class QueryJobsResponse(_message.Message):
    __slots__ = ("jobs", "next_page")
    JOBS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    jobs: _containers.RepeatedCompositeFieldContainer[_core_pb2.Job]
    next_page: _query_pb2.Pagination
    def __init__(self, jobs: _Optional[_Iterable[_Union[_core_pb2.Job, _Mapping]]] = ..., next_page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...

class GetJobPrototypeRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class GetJobPrototypeResponse(_message.Message):
    __slots__ = ("root_tasks", "job_name")
    ROOT_TASKS_FIELD_NUMBER: _ClassVar[int]
    JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    root_tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.SingleTaskSubmission]
    job_name: str
    def __init__(self, root_tasks: _Optional[_Iterable[_Union[_core_pb2.SingleTaskSubmission, _Mapping]]] = ..., job_name: _Optional[str] = ...) -> None: ...

class CloneJobRequest(_message.Message):
    __slots__ = ("job_id", "root_tasks_overrides", "job_name")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    ROOT_TASKS_OVERRIDES_FIELD_NUMBER: _ClassVar[int]
    JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    root_tasks_overrides: _containers.RepeatedCompositeFieldContainer[_core_pb2.SingleTaskSubmission]
    job_name: str
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., root_tasks_overrides: _Optional[_Iterable[_Union[_core_pb2.SingleTaskSubmission, _Mapping]]] = ..., job_name: _Optional[str] = ...) -> None: ...

class GetJobStateCountsRequest(_message.Message):
    __slots__ = ("time_interval",)
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    time_interval: _query_pb2.TimeInterval
    def __init__(self, time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ...) -> None: ...

class GetJobStateCountsResponse(_message.Message):
    __slots__ = ("state_counts", "total_jobs")
    STATE_COUNTS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_JOBS_FIELD_NUMBER: _ClassVar[int]
    state_counts: _containers.RepeatedCompositeFieldContainer[JobStateCount]
    total_jobs: int
    def __init__(self, state_counts: _Optional[_Iterable[_Union[JobStateCount, _Mapping]]] = ..., total_jobs: _Optional[int] = ...) -> None: ...

class JobStateCount(_message.Message):
    __slots__ = ("state", "count")
    STATE_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    state: _core_pb2.JobState
    count: int
    def __init__(self, state: _Optional[_Union[_core_pb2.JobState, str]] = ..., count: _Optional[int] = ...) -> None: ...

class GetTaskQueueStatsRequest(_message.Message):
    __slots__ = ("job_time_interval", "job_max_age")
    JOB_TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    JOB_MAX_AGE_FIELD_NUMBER: _ClassVar[int]
    job_time_interval: _query_pb2.TimeInterval
    job_max_age: _duration_pb2.Duration
    def __init__(self, job_time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., job_max_age: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class GetTaskQueueStatsResponse(_message.Message):
    __slots__ = ("waiting_jobs", "running_jobs", "queued_tasks", "oldest_waiting_job")
    WAITING_JOBS_FIELD_NUMBER: _ClassVar[int]
    RUNNING_JOBS_FIELD_NUMBER: _ClassVar[int]
    QUEUED_TASKS_FIELD_NUMBER: _ClassVar[int]
    OLDEST_WAITING_JOB_FIELD_NUMBER: _ClassVar[int]
    waiting_jobs: int
    running_jobs: int
    queued_tasks: int
    oldest_waiting_job: _core_pb2.Job
    def __init__(self, waiting_jobs: _Optional[int] = ..., running_jobs: _Optional[int] = ..., queued_tasks: _Optional[int] = ..., oldest_waiting_job: _Optional[_Union[_core_pb2.Job, _Mapping]] = ...) -> None: ...
