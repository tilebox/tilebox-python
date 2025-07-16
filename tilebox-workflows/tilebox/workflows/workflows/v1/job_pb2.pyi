from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from tilebox.workflows.workflows.v1 import diagram_pb2 as _diagram_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

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
    __slots__ = ("tasks", "job_name", "trace_parent", "automation_id")
    TASKS_FIELD_NUMBER: _ClassVar[int]
    JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    AUTOMATION_ID_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskSubmission]
    job_name: str
    trace_parent: str
    automation_id: _id_pb2.ID
    def __init__(self, tasks: _Optional[_Iterable[_Union[_core_pb2.TaskSubmission, _Mapping]]] = ..., job_name: _Optional[str] = ..., trace_parent: _Optional[str] = ..., automation_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class GetJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

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
    __slots__ = ("time_interval", "id_interval", "automation_id")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    ID_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    AUTOMATION_ID_FIELD_NUMBER: _ClassVar[int]
    time_interval: _query_pb2.TimeInterval
    id_interval: _query_pb2.IDInterval
    automation_id: _id_pb2.ID
    def __init__(self, time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., id_interval: _Optional[_Union[_query_pb2.IDInterval, _Mapping]] = ..., automation_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class QueryJobsRequest(_message.Message):
    __slots__ = ("filters", "page")
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    filters: QueryFilters
    page: _query_pb2.Pagination
    def __init__(self, filters: _Optional[_Union[QueryFilters, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...

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
    root_tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskSubmission]
    job_name: str
    def __init__(self, root_tasks: _Optional[_Iterable[_Union[_core_pb2.TaskSubmission, _Mapping]]] = ..., job_name: _Optional[str] = ...) -> None: ...

class CloneJobRequest(_message.Message):
    __slots__ = ("job_id", "root_tasks_overrides", "job_name")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    ROOT_TASKS_OVERRIDES_FIELD_NUMBER: _ClassVar[int]
    JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    root_tasks_overrides: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskSubmission]
    job_name: str
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., root_tasks_overrides: _Optional[_Iterable[_Union[_core_pb2.TaskSubmission, _Mapping]]] = ..., job_name: _Optional[str] = ...) -> None: ...
