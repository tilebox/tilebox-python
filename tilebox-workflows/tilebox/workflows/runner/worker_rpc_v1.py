from __future__ import annotations

import importlib
import logging
import re
import signal
import threading
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from time import monotonic
from types import FrameType
from uuid import UUID, uuid4

from google.protobuf.duration_pb2 import Duration
from opentelemetry.context import attach, detach
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from tilebox.runner.worker.v1 import worker_pb2
from tilebox.workflows.cache import InMemoryCache, JobCache
from tilebox.workflows.data import ExecutionStats, Job, JobState, RunnerContext, Task as WorkflowTask, TaskIdentifier, TaskState
from tilebox.workflows.interceptors import Interceptor, InterceptorType
from tilebox.workflows.observability.execution_attributes import bind_execution_attributes, set_span_execution_attributes
from tilebox.workflows.observability.tracing import _get_tilebox_tracer_provider
from tilebox.workflows.task import ExecutionContext as ExecutionContextBase
from tilebox.workflows.task import FutureTask, TaskMeta
from tilebox.workflows.task import ProgressUpdate as TaskProgressUpdate
from tilebox.workflows.task import Task as TaskInstance

_PHASE1_RUNTIME_KIND = "python_uv"
_MAX_TASK_PROGRESS_INDICATORS = 1000
_LOGGER = logging.getLogger(__name__)
_TRACE_CONTEXT_PROPAGATOR = TraceContextTextMapPropagator()
_TRACEPARENT_PATTERN = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")


ProtocolVersion = worker_pb2.ProtocolVersion
HandshakeRequest = worker_pb2.HandshakeRequest
HandshakeResponse = worker_pb2.HandshakeResponse


StartWorkerRequest = worker_pb2.StartWorkerRequest
StartWorkerResponse = worker_pb2.StartWorkerResponse
StopWorkerRequest = worker_pb2.StopWorkerRequest
StopWorkerResponse = worker_pb2.StopWorkerResponse
ProgressUpdate = worker_pb2.ProgressUpdate
SubmittedTask = worker_pb2.SubmittedTask
ExecuteTaskRequest = worker_pb2.ExecuteTaskRequest
ExecuteTaskResponse = worker_pb2.ExecuteTaskResponse
ExecuteTaskStatus = worker_pb2.ExecuteTaskResponse.Status
CancelTaskRequest = worker_pb2.CancelTaskRequest
CancelTaskResponse = worker_pb2.CancelTaskResponse
HealthCheckRequest = worker_pb2.HealthCheckRequest
HealthCheckResponse = worker_pb2.HealthCheckResponse


def _duration_from_seconds(seconds: float) -> Duration:
    duration = Duration()
    duration.FromTimedelta(timedelta(seconds=seconds))
    return duration


@contextmanager
def _attach_trace_context(trace_context_bytes: bytes) -> Iterator[None]:
    if not trace_context_bytes:
        yield
        return

    try:
        trace_parent = trace_context_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        _LOGGER.debug("Ignoring worker trace context: non-UTF-8 trace_context bytes", exc_info=True)
        yield
        return

    if trace_parent == "":
        yield
        return

    normalized_trace_parent = trace_parent.lower()
    if not _TRACEPARENT_PATTERN.fullmatch(normalized_trace_parent):
        _LOGGER.debug("Ignoring worker trace context: invalid traceparent")
        yield
        return

    _, trace_id_hex, span_id_hex, _ = normalized_trace_parent.split("-")
    if trace_id_hex == "0" * 32 or span_id_hex == "0" * 16:
        _LOGGER.debug("Ignoring worker trace context: invalid traceparent")
        yield
        return

    try:
        extracted_context = _TRACE_CONTEXT_PROPAGATOR.extract({"traceparent": normalized_trace_parent})
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Ignoring worker trace context: invalid traceparent", exc_info=True)
        yield
        return

    token = attach(extracted_context)
    try:
        yield
    finally:
        detach(token)


@contextmanager
def _start_task_span(task_name: str, job_id: str, task_id: str) -> Iterator[None]:
    """Create a span for task execution under the currently propagated trace context."""
    tracer = _get_tilebox_tracer_provider().get_tracer("tilebox.com/observability")
    with tracer.start_as_current_span(f"task/{task_name}") as span:
        set_span_execution_attributes(span, job_id=job_id, task_id=task_id)
        yield


class ProtocolVersionMismatchError(ValueError):
    """Raised when supervisor and worker protocol versions are incompatible."""


class RequiredCapabilitiesMissingError(ValueError):
    """Raised when the worker does not provide required capabilities."""


class TaskExecutionCanceledError(RuntimeError):
    """Raised when a task should stop because cancellation was requested."""


def _canonical_entrypoint(entrypoint: str) -> str:
    return entrypoint.strip()


def _is_sha256_digest(value: str) -> bool:
    return value.startswith("sha256:") and len(value) > len("sha256:")


def _basic_start_worker_readiness_error(request: StartWorkerRequest) -> str | None:
    checks = (
        (request.runtime_kind != _PHASE1_RUNTIME_KIND, f"Unsupported runtime kind '{request.runtime_kind}'"),
        (request.environment_digest == "", "Missing environment digest"),
        (not _is_sha256_digest(request.environment_digest), "Invalid environment digest format"),
        (request.artifact_digest == "", "Missing artifact digest"),
        (not _is_sha256_digest(request.artifact_digest), "Invalid artifact digest format"),
        (request.artifact_uri.strip() == "", "Missing artifact URI"),
    )
    for failed, message in checks:
        if failed:
            return message

    return None


def _import_task_class(entrypoint: str) -> type:
    """Import a task class from 'module:ClassName' entrypoint string."""
    if ":" not in entrypoint:
        msg = f"Invalid entrypoint format '{entrypoint}', expected 'module:ClassName'"
        raise ValueError(msg)

    module_name, _, class_name = entrypoint.partition(":")
    if not module_name or not class_name:
        msg = f"Invalid entrypoint format '{entrypoint}', module and class must be non-empty"
        raise ValueError(msg)

    module = importlib.import_module(module_name)
    task_class = getattr(module, class_name, None)
    if task_class is None:
        msg = f"Entrypoint class '{class_name}' not found in module '{module_name}'"
        raise ValueError(msg)

    return task_class


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        msg = f"Invalid {field_name}: {value!r}"
        raise ValueError(msg) from error


def _parse_optional_uuid(value: str, field_name: str) -> UUID | None:
    trimmed = value.strip()
    if trimmed == "":
        return None
    return _parse_uuid(trimmed, field_name)


def _parse_depends_on(values: Sequence[str]) -> list[UUID]:
    return [_parse_uuid(value, "task_depends_on") for value in values]


def _job_from_request(request: ExecuteTaskRequest, job_id: UUID) -> Job:
    execution_stats = ExecutionStats(
        first_task_started_at=None,
        last_task_stopped_at=None,
        compute_time=timedelta(0),
        elapsed_time=timedelta(0),
        parallelism=0.0,
        total_tasks=0,
        tasks_by_state={},
    )
    return Job(
        id=job_id,
        name=request.job_name,
        trace_parent=request.job_trace_parent,
        state=JobState.STARTED,
        submitted_at=datetime.now(tz=timezone.utc),
        progress=[],
        execution_stats=execution_stats,
    )


def _task_from_request(request: ExecuteTaskRequest) -> WorkflowTask:
    if request.task_retry_count < 0:
        msg = f"Invalid task_retry_count: {request.task_retry_count}"
        raise ValueError(msg)

    task_id = _parse_uuid(request.task_id, "task_id")
    job_id = _parse_uuid(request.job_id, "job_id")

    return WorkflowTask(
        id=task_id,
        identifier=TaskIdentifier.from_name_and_version(request.task_identifier_name, request.task_identifier_version),
        state=TaskState.RUNNING,
        input=request.task_input,
        display=request.task_display or None,
        job=_job_from_request(request, job_id),
        parent_id=_parse_optional_uuid(request.task_parent_id, "task_parent_id"),
        depends_on=_parse_depends_on(request.task_depends_on),
        retry_count=request.task_retry_count,
    )


def _response_display(context: "WorkerExecutionContext | None", fallback_display: str) -> str:
    if context is None:
        return fallback_display

    display = context.current_task.display
    if display is None:
        return fallback_display
    return display


@dataclass(slots=True)
class _WorkerInstanceState:
    ready: bool = True
    current_task_id: str | None = None
    cancellation_event: threading.Event | None = None


class _TrackedProgressUpdate(TaskProgressUpdate):
    def __init__(self, label: str | None) -> None:
        super().__init__(label)
        self.total = 0
        self.completed = 0

    def add(self, count: int) -> None:
        self.total += count
        super().add(count)

    def done(self, count: int) -> None:
        self.completed += count
        super().done(count)


class WorkerExecutionContext(ExecutionContextBase):
    def __init__(
        self,
        runner_context: RunnerContext,
        job_cache: JobCache,
        fallback_cluster_slug: str,
        cancellation_event: threading.Event,
        current_task: WorkflowTask,
    ) -> None:
        self._runner_context = runner_context
        self.job_cache = job_cache
        self.current_task = current_task
        self._fallback_cluster_slug = fallback_cluster_slug
        self._cancellation_event = cancellation_event
        self._sub_tasks: list[FutureTask] = []
        self._progress_indicators: dict[str | None, _TrackedProgressUpdate] = {}

    def submit_subtask(
        self,
        task: TaskInstance,
        depends_on: FutureTask | list[FutureTask] | None = None,
        cluster: str | None = None,
        max_retries: int = 0,
        optional: bool = False,
    ) -> FutureTask:
        dependencies: list[int] = []

        if depends_on is None:
            depends_on = []
        elif isinstance(depends_on, FutureTask):
            depends_on = [depends_on]
        elif not isinstance(depends_on, list):
            msg = f"Invalid dependency. Expected FutureTask or list[FutureTask], got {type(depends_on)}"
            raise TypeError(msg)

        for dependency in depends_on:
            if not isinstance(dependency, FutureTask):
                msg = f"Invalid dependency. Expected FutureTask, got {type(dependency)}"
                raise TypeError(msg)
            if dependency.index >= len(self._sub_tasks):
                msg = f"Dependent task {dependency.index} does not exist"
                raise ValueError(msg)
            dependencies.append(dependency.index)

        subtask = FutureTask(
            index=len(self._sub_tasks),
            task=task,
            depends_on=dependencies,
            cluster=cluster,
            max_retries=max_retries,
            optional=optional,
        )
        self._sub_tasks.append(subtask)
        return subtask

    def submit_subtasks(
        self,
        tasks: Sequence[TaskInstance],
        depends_on: FutureTask | list[FutureTask] | None = None,
        cluster: str | None = None,
        max_retries: int = 0,
        optional: bool = False,
    ) -> list[FutureTask]:
        return [
            self.submit_subtask(
                task,
                depends_on=depends_on,
                cluster=cluster,
                max_retries=max_retries,
                optional=optional,
            )
            for task in tasks
        ]

    def submit_batch(
        self,
        tasks: Sequence[TaskInstance],
        cluster: str | None = None,
        max_retries: int = 0,
    ) -> list[FutureTask]:
        return self.submit_subtasks(tasks=tasks, cluster=cluster, max_retries=max_retries)

    @property
    def runner_context(self) -> RunnerContext:
        return self._runner_context

    def progress(self, label: str | None = None) -> _TrackedProgressUpdate:
        if label == "":
            label = None

        if label in self._progress_indicators:
            return self._progress_indicators[label]

        if len(self._progress_indicators) > _MAX_TASK_PROGRESS_INDICATORS:
            msg = f"Cannot create more than {_MAX_TASK_PROGRESS_INDICATORS} progress indicators per task."
            raise ValueError(msg)

        progress_update = _TrackedProgressUpdate(label)
        self._progress_indicators[label] = progress_update
        return progress_update

    def is_cancellation_requested(self) -> bool:
        return self._cancellation_event.is_set()

    def raise_if_cancellation_requested(self, reason: str = "Task was canceled") -> None:
        if self.is_cancellation_requested():
            raise TaskExecutionCanceledError(reason)

    def progress_updates(self) -> tuple[ProgressUpdate, ...]:
        return tuple(
            ProgressUpdate(label=label or "", total=progress.total, done=progress.completed)
            for label, progress in self._progress_indicators.items()
        )

    def submitted_subtasks(self) -> tuple[SubmittedTask, ...]:
        submitted: list[SubmittedTask] = []
        for subtask in self._sub_tasks:
            identifier = subtask.identifier()
            submitted.append(
                SubmittedTask(
                    input=subtask.input(),
                    cluster_slug=subtask.cluster or self._fallback_cluster_slug,
                    identifier_name=identifier.name,
                    identifier_version=identifier.version,
                    display=subtask.display(),
                    max_retries=subtask.max_retries,
                    depends_on=tuple(subtask.depends_on),
                    optional=subtask.optional,
                )
            )
        return tuple(submitted)


def _execute_task_with_interceptors(
    task: TaskInstance,
    context: WorkerExecutionContext,
    additional_interceptors: Sequence[Interceptor],
) -> None:
    interceptors = [*additional_interceptors, *TaskMeta.for_task(task).interceptors]

    next_function = task.execute
    for interceptor in reversed(interceptors):
        next_function = partial(interceptor, task, next_function)

    next_function(context)


class PythonWorkerShim:
    def __init__(  # noqa: PLR0913
        self,
        tasks: Sequence[type[TaskInstance]] | None = None,
        *,
        worker_protocol: ProtocolVersion | None = None,
        worker_runtime: str = "python",
        worker_id: str | None = None,
        capabilities: Collection[str] | None = None,
        runner_context: RunnerContext | None = None,
        cache: JobCache | None = None,
        default_cluster_slug: str = "",
        expected_environment_digest: str | None = None,
        expected_artifact_digest: str | None = None,
        expected_entrypoint: str | None = None,
    ) -> None:
        worker_protocol_message = worker_protocol
        if worker_protocol_message is None:
            worker_protocol_message = ProtocolVersion(major=1, minor=0)
        self._worker_protocol = ProtocolVersion(
            major=worker_protocol_message.major,
            minor=worker_protocol_message.minor,
        )
        self._worker_runtime = worker_runtime
        self._worker_id = worker_id or str(uuid4())
        self._capabilities = tuple(
            sorted(capabilities or {"execute_task", "cancel_task", "progress_updates", "submitted_subtasks"})
        )
        self._runner_context = runner_context or RunnerContext()
        self._cache = cache or InMemoryCache()
        self._default_cluster_slug = default_cluster_slug
        self._expected_environment_digest = expected_environment_digest
        self._expected_artifact_digest = expected_artifact_digest
        self._expected_entrypoint = None if expected_entrypoint is None else _canonical_entrypoint(expected_entrypoint)
        self._interceptors: list[Interceptor] = []
        self._registered_tasks: dict[TaskIdentifier, type[TaskInstance]] = {}

        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._workers: dict[str, _WorkerInstanceState] = {}

        for task in tasks or ():
            self.register(task)

    def register(self, task: type[TaskInstance]) -> None:
        metadata = TaskMeta.for_task(task)
        if not metadata.executable:
            msg = f"Task {task.__name__} is not executable. It must define an execute method."
            raise ValueError(msg)
        if metadata.identifier in self._registered_tasks:
            msg = (
                "Duplicate task identifier: "
                f"A task '{metadata.identifier.name}' with version '{metadata.identifier.version}' is already registered."
            )
            raise ValueError(msg)
        self._registered_tasks[metadata.identifier] = task

    def add_interceptor(self, interceptor: InterceptorType) -> None:
        if not hasattr(interceptor, "__original_interceptor_func__"):
            msg = "Interceptor must be created with @execution_interceptor decorator."
            raise ValueError(msg)
        self._interceptors.append(interceptor.__original_interceptor_func__)

    def handshake(
        self,
        request: HandshakeRequest,
        *,
        required_capabilities: Collection[str] = (),
    ) -> HandshakeResponse:
        supervisor_protocol = request.supervisor_protocol
        worker_protocol = self._worker_protocol

        if supervisor_protocol.major != worker_protocol.major:
            msg = (
                "Protocol major version mismatch: "
                f"supervisor={supervisor_protocol.major}, worker={worker_protocol.major}"
            )
            raise ProtocolVersionMismatchError(msg)

        if supervisor_protocol.minor < worker_protocol.minor:
            msg = (
                "Protocol minor version mismatch: "
                f"supervisor={supervisor_protocol.minor}, worker={worker_protocol.minor}"
            )
            raise ProtocolVersionMismatchError(msg)

        if request.worker_runtime != self._worker_runtime:
            msg = f"Worker runtime mismatch: supervisor expects '{request.worker_runtime}'"
            raise ProtocolVersionMismatchError(msg)

        missing_capabilities = sorted(set(required_capabilities) - set(self._capabilities))
        if missing_capabilities:
            msg = f"Missing required capabilities: {', '.join(missing_capabilities)}"
            raise RequiredCapabilitiesMissingError(msg)

        return HandshakeResponse(
            worker_protocol=ProtocolVersion(major=worker_protocol.major, minor=worker_protocol.minor),
            capabilities=list(self._capabilities),
            worker_id=self._worker_id,
            worker_runtime=self._worker_runtime,
        )

    def start_worker(self, request: StartWorkerRequest) -> StartWorkerResponse:
        if self._shutdown_event.is_set():
            return StartWorkerResponse(worker_instance_id="", ready=False, message="Worker shim is shutting down")

        readiness_error = self._start_worker_readiness_error(request)
        if readiness_error is not None:
            return StartWorkerResponse(
                worker_instance_id="",
                ready=False,
                message=readiness_error,
            )

        # Dynamically import and register tasks from the entrypoint if no
        # tasks were pre-registered.  The entrypoint may be a single
        # "module:Class" string or a comma-separated list of them.  The worker
        # process is expected to already run inside the correct uv environment
        # (deps installed), so the entrypoint modules are importable on
        # sys.path.
        if len(self._registered_tasks) == 0:
            raw_entrypoint = _canonical_entrypoint(request.entrypoint)
            entrypoints = [ep.strip() for ep in raw_entrypoint.split(",") if ep.strip()]
            if not entrypoints:
                return StartWorkerResponse(
                    worker_instance_id="",
                    ready=False,
                    message="No entrypoints provided",
                )

            for entrypoint in entrypoints:
                try:
                    task_class = _import_task_class(entrypoint)
                except Exception as exc:  # noqa: BLE001
                    return StartWorkerResponse(
                        worker_instance_id="",
                        ready=False,
                        message=f"Failed to load task from entrypoint '{entrypoint}': {exc}",
                    )

                if not (isinstance(task_class, type) and issubclass(task_class, TaskInstance)):
                    return StartWorkerResponse(
                        worker_instance_id="",
                        ready=False,
                        message=f"Entrypoint '{entrypoint}' does not resolve to a Task subclass",
                    )

                try:
                    self.register(task_class)
                except ValueError as exc:
                    return StartWorkerResponse(
                        worker_instance_id="",
                        ready=False,
                        message=str(exc),
                    )

        worker_instance_id = str(uuid4())
        with self._lock:
            self._workers[worker_instance_id] = _WorkerInstanceState(ready=True)

        return StartWorkerResponse(worker_instance_id=worker_instance_id, ready=True, message="ready")

    def _start_worker_readiness_error(self, request: StartWorkerRequest) -> str | None:
        basic_error = _basic_start_worker_readiness_error(request)
        if basic_error is not None:
            return basic_error

        requested_entrypoint = _canonical_entrypoint(request.entrypoint)

        if (
            self._expected_environment_digest is not None
            and request.environment_digest != self._expected_environment_digest
        ):
            return (
                "Worker environment digest mismatch: "
                f"expected '{self._expected_environment_digest}', got '{request.environment_digest}'"
            )

        if self._expected_artifact_digest is not None and request.artifact_digest != self._expected_artifact_digest:
            return (
                "Worker artifact digest mismatch: "
                f"expected '{self._expected_artifact_digest}', got '{request.artifact_digest}'"
            )

        if self._expected_entrypoint is not None and requested_entrypoint != self._expected_entrypoint:
            return f"Worker entrypoint mismatch: expected '{self._expected_entrypoint}', got '{requested_entrypoint}'"

        return None

    def stop_worker(self, request: StopWorkerRequest) -> StopWorkerResponse:
        with self._lock:
            state = self._workers.pop(request.worker_instance_id, None)

        if state is None:
            return StopWorkerResponse(stopped=False)

        if state.cancellation_event is not None:
            state.cancellation_event.set()

        return StopWorkerResponse(stopped=True)

    def health_check(self, request: HealthCheckRequest) -> HealthCheckResponse:
        with self._lock:
            state = self._workers.get(request.worker_instance_id)

        if state is None:
            return HealthCheckResponse(healthy=False, message="Unknown worker instance")
        if self._shutdown_event.is_set():
            return HealthCheckResponse(healthy=False, message="Worker shim is shutting down")
        if not state.ready:
            return HealthCheckResponse(healthy=False, message="Worker is not ready")
        return HealthCheckResponse(healthy=True, message="ok")

    def _registered_task_class(self, task_identifier: TaskIdentifier) -> type[TaskInstance]:
        task_class = self._registered_tasks.get(task_identifier)
        if task_class is None:
            msg = f"Unknown task identifier {task_identifier.name}@{task_identifier.version}"
            raise ValueError(msg)
        return task_class

    def execute_task(self, request: ExecuteTaskRequest) -> ExecuteTaskResponse:  # noqa: PLR0911
        start_time = monotonic()

        context: WorkerExecutionContext | None = None
        task_id = request.task_id
        cancellation_event = threading.Event()

        with self._lock:
            if self._shutdown_event.is_set():
                return ExecuteTaskResponse(
                    status=ExecuteTaskStatus.STATUS_CANCELED,
                    display=request.task_display,
                    error_message="Worker shim is shutting down",
                    execution_duration=_duration_from_seconds(monotonic() - start_time),
                )

            worker_state = self._workers.get(request.worker_instance_id)
            if worker_state is None or not worker_state.ready:
                return ExecuteTaskResponse(
                    status=ExecuteTaskStatus.STATUS_FAILED,
                    display=request.task_display,
                    error_message="Unknown or not-ready worker instance",
                    was_workflow_error=True,
                    execution_duration=_duration_from_seconds(monotonic() - start_time),
                )

            if worker_state.current_task_id is not None:
                return ExecuteTaskResponse(
                    status=ExecuteTaskStatus.STATUS_FAILED,
                    display=request.task_display,
                    error_message=(
                        f"Worker instance '{request.worker_instance_id}' is already running task "
                        f"'{worker_state.current_task_id}'"
                    ),
                    was_workflow_error=True,
                    execution_duration=_duration_from_seconds(monotonic() - start_time),
                )

            worker_state.current_task_id = task_id
            worker_state.cancellation_event = cancellation_event

        try:
            task_identifier = TaskIdentifier.from_name_and_version(
                request.task_identifier_name,
                request.task_identifier_version,
            )

            task_class = self._registered_task_class(task_identifier)

            cache_scope = request.task_id
            if request.trace_context:
                cache_scope = request.trace_context.hex()

            current_task = _task_from_request(request)
            context = WorkerExecutionContext(
                runner_context=self._runner_context,
                job_cache=self._cache.group(cache_scope),
                fallback_cluster_slug=self._default_cluster_slug,
                cancellation_event=cancellation_event,
                current_task=current_task,
            )
            context.raise_if_cancellation_requested()

            task_instance = task_class._deserialize(request.task_input, self._runner_context)  # noqa: SLF001
            with (
                _attach_trace_context(request.trace_context),
                _start_task_span(request.task_identifier_name, request.job_id, request.task_id),
                bind_execution_attributes(job_id=request.job_id, task_id=request.task_id),
            ):
                _execute_task_with_interceptors(task_instance, context, self._interceptors)

            if context.is_cancellation_requested() or self._shutdown_event.is_set():
                return ExecuteTaskResponse(
                    status=ExecuteTaskStatus.STATUS_CANCELED,
                    display=_response_display(context, request.task_display),
                    error_message="Task was canceled",
                    was_workflow_error=False,
                    progress_updates=context.progress_updates(),
                    submitted_subtasks=context.submitted_subtasks(),
                    execution_duration=_duration_from_seconds(monotonic() - start_time),
                )

            return ExecuteTaskResponse(
                status=ExecuteTaskStatus.STATUS_COMPUTED,
                display=_response_display(context, request.task_display),
                progress_updates=context.progress_updates(),
                submitted_subtasks=context.submitted_subtasks(),
                execution_duration=_duration_from_seconds(monotonic() - start_time),
            )
        except TaskExecutionCanceledError as error:
            return ExecuteTaskResponse(
                status=ExecuteTaskStatus.STATUS_CANCELED,
                display=_response_display(context, request.task_display),
                error_message=str(error),
                was_workflow_error=False,
                progress_updates=[] if context is None else context.progress_updates(),
                submitted_subtasks=[] if context is None else context.submitted_subtasks(),
                execution_duration=_duration_from_seconds(monotonic() - start_time),
            )
        except Exception as error:  # noqa: BLE001
            return ExecuteTaskResponse(
                status=ExecuteTaskStatus.STATUS_FAILED,
                display=_response_display(context, request.task_display),
                error_message=repr(error),
                was_workflow_error=True,
                progress_updates=[] if context is None else context.progress_updates(),
                submitted_subtasks=[] if context is None else context.submitted_subtasks(),
                execution_duration=_duration_from_seconds(monotonic() - start_time),
            )
        finally:
            with self._lock:
                worker_state = self._workers.get(request.worker_instance_id)
                if worker_state is not None and worker_state.current_task_id == task_id:
                    worker_state.current_task_id = None
                    worker_state.cancellation_event = None

    def cancel_task(self, request: CancelTaskRequest) -> CancelTaskResponse:
        with self._lock:
            worker_state = self._workers.get(request.worker_instance_id)
            if worker_state is None:
                return CancelTaskResponse(accepted=False)

            if worker_state.current_task_id != request.task_id:
                return CancelTaskResponse(accepted=False)

            if worker_state.cancellation_event is None:
                return CancelTaskResponse(accepted=False)

            worker_state.cancellation_event.set()

        return CancelTaskResponse(accepted=True)

    def request_shutdown(self, reason: str = "") -> bool:
        _ = reason
        if self._shutdown_event.is_set():
            return False

        self._shutdown_event.set()
        with self._lock:
            cancellation_events = [
                worker_state.cancellation_event
                for worker_state in self._workers.values()
                if worker_state.cancellation_event is not None
            ]

        for cancellation_event in cancellation_events:
            cancellation_event.set()

        return True

    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()

    @contextmanager
    def graceful_shutdown(self) -> Iterator[None]:
        if threading.current_thread() is not threading.main_thread():
            yield
            return

        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        def _handler(signum: int, frame: FrameType | None) -> None:
            already_shutting_down = self.is_shutting_down()
            self.request_shutdown(reason=f"signal:{signum}")
            if already_shutting_down:
                original_handler = original_sigint if signum == signal.SIGINT else original_sigterm

                if callable(original_handler):
                    original_handler(signum, frame)

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)
        try:
            yield
        finally:
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)
