from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProtocolVersion(_message.Message):
    __slots__ = ("major", "minor")
    MAJOR_FIELD_NUMBER: _ClassVar[int]
    MINOR_FIELD_NUMBER: _ClassVar[int]
    major: int
    minor: int
    def __init__(self, major: _Optional[int] = ..., minor: _Optional[int] = ...) -> None: ...

class HandshakeRequest(_message.Message):
    __slots__ = ("supervisor_protocol", "worker_runtime")
    SUPERVISOR_PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    WORKER_RUNTIME_FIELD_NUMBER: _ClassVar[int]
    supervisor_protocol: ProtocolVersion
    worker_runtime: str
    def __init__(self, supervisor_protocol: _Optional[_Union[ProtocolVersion, _Mapping]] = ..., worker_runtime: _Optional[str] = ...) -> None: ...

class HandshakeResponse(_message.Message):
    __slots__ = ("worker_protocol", "capabilities", "worker_id", "worker_runtime")
    WORKER_PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_RUNTIME_FIELD_NUMBER: _ClassVar[int]
    worker_protocol: ProtocolVersion
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    worker_id: str
    worker_runtime: str
    def __init__(self, worker_protocol: _Optional[_Union[ProtocolVersion, _Mapping]] = ..., capabilities: _Optional[_Iterable[str]] = ..., worker_id: _Optional[str] = ..., worker_runtime: _Optional[str] = ...) -> None: ...

class StartWorkerRequest(_message.Message):
    __slots__ = ("environment_digest", "runtime_kind", "artifact_uri", "artifact_digest", "entrypoint")
    ENVIRONMENT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_KIND_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_URI_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    ENTRYPOINT_FIELD_NUMBER: _ClassVar[int]
    environment_digest: str
    runtime_kind: str
    artifact_uri: str
    artifact_digest: str
    entrypoint: str
    def __init__(self, environment_digest: _Optional[str] = ..., runtime_kind: _Optional[str] = ..., artifact_uri: _Optional[str] = ..., artifact_digest: _Optional[str] = ..., entrypoint: _Optional[str] = ...) -> None: ...

class StartWorkerResponse(_message.Message):
    __slots__ = ("worker_instance_id", "ready", "message")
    WORKER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    READY_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    worker_instance_id: str
    ready: bool
    message: str
    def __init__(self, worker_instance_id: _Optional[str] = ..., ready: bool = ..., message: _Optional[str] = ...) -> None: ...

class StopWorkerRequest(_message.Message):
    __slots__ = ("worker_instance_id", "reason")
    WORKER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    worker_instance_id: str
    reason: str
    def __init__(self, worker_instance_id: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class StopWorkerResponse(_message.Message):
    __slots__ = ("stopped",)
    STOPPED_FIELD_NUMBER: _ClassVar[int]
    stopped: bool
    def __init__(self, stopped: bool = ...) -> None: ...

class ProgressUpdate(_message.Message):
    __slots__ = ("label", "total", "done")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    label: str
    total: int
    done: int
    def __init__(self, label: _Optional[str] = ..., total: _Optional[int] = ..., done: _Optional[int] = ...) -> None: ...

class SubmittedTask(_message.Message):
    __slots__ = ("input", "cluster_slug", "identifier_name", "identifier_version", "display", "max_retries", "depends_on", "optional")
    INPUT_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_NAME_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_VERSION_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_FIELD_NUMBER: _ClassVar[int]
    DEPENDS_ON_FIELD_NUMBER: _ClassVar[int]
    OPTIONAL_FIELD_NUMBER: _ClassVar[int]
    input: bytes
    cluster_slug: str
    identifier_name: str
    identifier_version: str
    display: str
    max_retries: int
    depends_on: _containers.RepeatedScalarFieldContainer[int]
    optional: bool
    def __init__(self, input: _Optional[bytes] = ..., cluster_slug: _Optional[str] = ..., identifier_name: _Optional[str] = ..., identifier_version: _Optional[str] = ..., display: _Optional[str] = ..., max_retries: _Optional[int] = ..., depends_on: _Optional[_Iterable[int]] = ..., optional: bool = ...) -> None: ...

class ExecuteTaskRequest(_message.Message):
    __slots__ = ("worker_instance_id", "task_id", "task_identifier_name", "task_identifier_version", "task_input", "task_display", "trace_context", "job_id", "job_name", "job_trace_parent", "task_parent_id", "task_depends_on", "task_retry_count")
    WORKER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_IDENTIFIER_NAME_FIELD_NUMBER: _ClassVar[int]
    TASK_IDENTIFIER_VERSION_FIELD_NUMBER: _ClassVar[int]
    TASK_INPUT_FIELD_NUMBER: _ClassVar[int]
    TASK_DISPLAY_FIELD_NUMBER: _ClassVar[int]
    TRACE_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_NAME_FIELD_NUMBER: _ClassVar[int]
    JOB_TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    TASK_PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_DEPENDS_ON_FIELD_NUMBER: _ClassVar[int]
    TASK_RETRY_COUNT_FIELD_NUMBER: _ClassVar[int]
    worker_instance_id: str
    task_id: str
    task_identifier_name: str
    task_identifier_version: str
    task_input: bytes
    task_display: str
    trace_context: bytes
    job_id: str
    job_name: str
    job_trace_parent: str
    task_parent_id: str
    task_depends_on: _containers.RepeatedScalarFieldContainer[str]
    task_retry_count: int
    def __init__(self, worker_instance_id: _Optional[str] = ..., task_id: _Optional[str] = ..., task_identifier_name: _Optional[str] = ..., task_identifier_version: _Optional[str] = ..., task_input: _Optional[bytes] = ..., task_display: _Optional[str] = ..., trace_context: _Optional[bytes] = ..., job_id: _Optional[str] = ..., job_name: _Optional[str] = ..., job_trace_parent: _Optional[str] = ..., task_parent_id: _Optional[str] = ..., task_depends_on: _Optional[_Iterable[str]] = ..., task_retry_count: _Optional[int] = ...) -> None: ...

class ExecuteTaskResponse(_message.Message):
    __slots__ = ("status", "display", "error_message", "was_workflow_error", "progress_updates", "submitted_subtasks", "execution_duration")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_UNSPECIFIED: _ClassVar[ExecuteTaskResponse.Status]
        STATUS_COMPUTED: _ClassVar[ExecuteTaskResponse.Status]
        STATUS_FAILED: _ClassVar[ExecuteTaskResponse.Status]
        STATUS_RETRYABLE_FAILURE: _ClassVar[ExecuteTaskResponse.Status]
        STATUS_CANCELED: _ClassVar[ExecuteTaskResponse.Status]
    STATUS_UNSPECIFIED: ExecuteTaskResponse.Status
    STATUS_COMPUTED: ExecuteTaskResponse.Status
    STATUS_FAILED: ExecuteTaskResponse.Status
    STATUS_RETRYABLE_FAILURE: ExecuteTaskResponse.Status
    STATUS_CANCELED: ExecuteTaskResponse.Status
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    WAS_WORKFLOW_ERROR_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_UPDATES_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_SUBTASKS_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_DURATION_FIELD_NUMBER: _ClassVar[int]
    status: ExecuteTaskResponse.Status
    display: str
    error_message: str
    was_workflow_error: bool
    progress_updates: _containers.RepeatedCompositeFieldContainer[ProgressUpdate]
    submitted_subtasks: _containers.RepeatedCompositeFieldContainer[SubmittedTask]
    execution_duration: _duration_pb2.Duration
    def __init__(self, status: _Optional[_Union[ExecuteTaskResponse.Status, str]] = ..., display: _Optional[str] = ..., error_message: _Optional[str] = ..., was_workflow_error: bool = ..., progress_updates: _Optional[_Iterable[_Union[ProgressUpdate, _Mapping]]] = ..., submitted_subtasks: _Optional[_Iterable[_Union[SubmittedTask, _Mapping]]] = ..., execution_duration: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class CancelTaskRequest(_message.Message):
    __slots__ = ("worker_instance_id", "task_id", "reason")
    WORKER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    worker_instance_id: str
    task_id: str
    reason: str
    def __init__(self, worker_instance_id: _Optional[str] = ..., task_id: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class CancelTaskResponse(_message.Message):
    __slots__ = ("accepted",)
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    def __init__(self, accepted: bool = ...) -> None: ...

class HealthCheckRequest(_message.Message):
    __slots__ = ("worker_instance_id",)
    WORKER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    worker_instance_id: str
    def __init__(self, worker_instance_id: _Optional[str] = ...) -> None: ...

class HealthCheckResponse(_message.Message):
    __slots__ = ("healthy", "message")
    HEALTHY_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    healthy: bool
    message: str
    def __init__(self, healthy: bool = ..., message: _Optional[str] = ...) -> None: ...
