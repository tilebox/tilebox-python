import threading
import time
from typing import ClassVar
from uuid import uuid4

import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.trace.export import SpanProcessor
from opentelemetry.trace import get_current_span

from tilebox.workflows import ExecutionContext, Task
from tilebox.workflows.observability import tracing
from tilebox.workflows.runner import worker_rpc_v1
from tilebox.workflows.runner.worker_rpc_v1 import (
    CancelTaskRequest,
    ExecuteTaskRequest,
    ExecuteTaskStatus,
    HandshakeRequest,
    ProtocolVersion,
    ProtocolVersionMismatchError,
    PythonWorkerShim,
    StartWorkerRequest,
)


class _NoopSpanProcessor(SpanProcessor):
    def on_start(self, span: Span, parent_context: object | None = None) -> None:
        _ = span, parent_context

    def on_end(self, span: ReadableSpan) -> None:
        _ = span

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        _ = timeout_millis
        return True


@pytest.fixture(autouse=True)
def disable_worker_shim_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
    def noop_span_exporter(*_args: object, **_kwargs: object) -> _NoopSpanProcessor:
        return _NoopSpanProcessor()

    def noop_logger_provider(service: object, url: str, token: str | None) -> LoggerProvider:
        _ = service, url, token
        return LoggerProvider()

    monkeypatch.setattr(tracing, "_otel_span_exporter", noop_span_exporter)
    monkeypatch.setattr(
        worker_rpc_v1,
        "_create_tilebox_logger_provider",
        noop_logger_provider,
    )


class ChildTask(Task):
    value: int


class EmitSubtasksTask(Task):
    count: int

    def execute(self, context: ExecutionContext) -> None:
        progress = context.progress("items")
        progress.add(self.count)
        progress.done(2)

        first = context.submit_subtask(ChildTask(value=1), max_retries=2)
        context.submit_subtask(ChildTask(value=2), depends_on=[first], optional=True)


class FailingTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context
        msg = "boom"
        raise RuntimeError(msg)


class CooperativeCancelTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        while True:
            maybe_cancel = getattr(context, "raise_if_cancellation_requested", None)
            if callable(maybe_cancel):
                maybe_cancel()
            time.sleep(0.01)


class CaptureExecutionAttributesTask(Task):
    captured_trace_id: ClassVar[int | None] = None

    def execute(self, context: ExecutionContext) -> None:
        _ = context
        CaptureExecutionAttributesTask.captured_trace_id = get_current_span().get_span_context().trace_id


class CaptureContextObservabilityTask(Task):
    captured_logger_name: ClassVar[str | None] = None
    captured_logger_attributes: ClassVar[dict[str, str]] = {}
    captured_tracer: ClassVar[object | None] = None

    def execute(self, context: ExecutionContext) -> None:
        CaptureContextObservabilityTask.captured_logger_name = context.logger._logger.name
        CaptureContextObservabilityTask.captured_logger_attributes = context.logger._attributes.copy()
        CaptureContextObservabilityTask.captured_tracer = context.tracer


class CacheWriteTask(Task):
    key: str
    value: str

    def execute(self, context: ExecutionContext) -> None:
        cache = context.job_cache  # ty: ignore[unresolved-attribute]
        cache[self.key] = self.value.encode("utf-8")


class CacheReadTask(Task):
    key: str
    expected_value: str

    def execute(self, context: ExecutionContext) -> None:
        cache = context.job_cache  # ty: ignore[unresolved-attribute]
        assert cache[self.key] == self.expected_value.encode("utf-8")


class CacheMissingKeyTask(Task):
    key: str

    def execute(self, context: ExecutionContext) -> None:
        cache = context.job_cache  # ty: ignore[unresolved-attribute]
        _ = cache[self.key]


def _started_worker(shim: PythonWorkerShim) -> str:
    response = shim.start_worker(
        StartWorkerRequest(
            environment_digest="sha256:env",
            runtime_kind="python_uv",
            artifact_uri="file:///artifact.tar.zst",
            artifact_digest="sha256:artifact",
            entrypoint="tilebox_worker:main",
        )
    )
    assert response.ready
    return response.worker_instance_id


def test_handshake_rejects_major_mismatch() -> None:
    shim = PythonWorkerShim(tasks=[EmitSubtasksTask])

    with pytest.raises(ProtocolVersionMismatchError):
        shim.handshake(
            HandshakeRequest(
                supervisor_protocol=ProtocolVersion(major=2, minor=0),
                worker_runtime="python",
            )
        )


def test_start_worker_requires_entrypoint_when_no_tasks_registered() -> None:
    shim = PythonWorkerShim()

    response = shim.start_worker(
        StartWorkerRequest(
            environment_digest="sha256:env",
            runtime_kind="python_uv",
            artifact_uri="file:///artifact.tar.zst",
            artifact_digest="sha256:artifact",
            entrypoint="",
        )
    )

    assert response.ready is False
    assert "no entrypoints provided" in response.message.lower()


def test_start_worker_accepts_pre_registered_tasks_without_entrypoint() -> None:
    shim = PythonWorkerShim(tasks=[EmitSubtasksTask])

    response = shim.start_worker(
        StartWorkerRequest(
            environment_digest="sha256:env",
            runtime_kind="python_uv",
            artifact_uri="file:///artifact.tar.zst",
            artifact_digest="sha256:artifact",
            entrypoint="",
        )
    )

    assert response.ready is True


def test_start_worker_rejects_mismatched_expected_digests() -> None:
    shim = PythonWorkerShim(
        tasks=[EmitSubtasksTask],
        expected_environment_digest="sha256:expected-env",
        expected_artifact_digest="sha256:expected-artifact",
        expected_entrypoint="tilebox_worker:main",
    )

    response = shim.start_worker(
        StartWorkerRequest(
            environment_digest="sha256:other-env",
            runtime_kind="python_uv",
            artifact_uri="file:///artifact.tar.zst",
            artifact_digest="sha256:other-artifact",
            entrypoint="tilebox_worker:main",
        )
    )

    assert response.ready is False
    assert "environment digest mismatch" in response.message.lower()


def test_execute_task_maps_progress_and_subtasks() -> None:
    shim = PythonWorkerShim(tasks=[EmitSubtasksTask], default_cluster_slug="cluster-a")
    worker_instance_id = _started_worker(shim)

    task = EmitSubtasksTask(count=5)
    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=str(uuid4()),
        job_id=str(uuid4()),
        task_identifier_name="EmitSubtasksTask",
        task_identifier_version="v0.0",
        task_input=task._serialize(),
        task_display="emit-subtasks",
    )

    response = shim.execute_task(request)

    assert response.status == ExecuteTaskStatus.STATUS_COMPUTED
    assert response.error_message == ""
    assert response.was_workflow_error is False

    assert len(response.progress_updates) == 1
    assert response.progress_updates[0].label == "items"
    assert response.progress_updates[0].total == 5
    assert response.progress_updates[0].done == 2

    assert len(response.submitted_subtasks) == 2
    first, second = response.submitted_subtasks
    assert first.cluster_slug == "cluster-a"
    assert first.identifier_name == "ChildTask"
    assert first.identifier_version == "v0.0"
    assert first.max_retries == 2
    assert list(first.depends_on) == []
    assert first.optional is False

    assert list(second.depends_on) == [0]
    assert second.optional is True


def test_execute_task_maps_failures() -> None:
    shim = PythonWorkerShim(tasks=[FailingTask])
    worker_instance_id = _started_worker(shim)

    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=str(uuid4()),
        job_id=str(uuid4()),
        task_identifier_name="FailingTask",
        task_identifier_version="v0.0",
        task_input=FailingTask()._serialize(),
        task_display="failing-task",
    )

    response = shim.execute_task(request)

    assert response.status == ExecuteTaskStatus.STATUS_FAILED
    assert response.was_workflow_error is True
    assert "boom" in response.error_message


def test_execute_task_uses_shim_observability_logger_and_tracer() -> None:
    shim = PythonWorkerShim(tasks=[CaptureContextObservabilityTask], token="token")  # noqa: S106
    worker_instance_id = _started_worker(shim)

    CaptureContextObservabilityTask.captured_logger_name = None
    CaptureContextObservabilityTask.captured_logger_attributes = {}
    CaptureContextObservabilityTask.captured_tracer = None

    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=str(uuid4()),
        job_id=str(uuid4()),
        task_identifier_name="CaptureContextObservabilityTask",
        task_identifier_version="v0.0",
        task_input=CaptureContextObservabilityTask()._serialize(),
        task_display="capture-observability",
    )

    response = shim.execute_task(request)

    assert response.status == ExecuteTaskStatus.STATUS_COMPUTED
    assert CaptureContextObservabilityTask.captured_tracer is shim._tracer
    assert CaptureContextObservabilityTask.captured_logger_name == f"tilebox.workflows.clients.{shim._client_id}.tasks"
    assert CaptureContextObservabilityTask.captured_logger_attributes == {
        "job_id": request.job_id,
        "task_id": request.task_id,
    }


def test_execute_task_accepts_valid_trace_context() -> None:
    shim = PythonWorkerShim(tasks=[CaptureExecutionAttributesTask])
    worker_instance_id = _started_worker(shim)

    CaptureExecutionAttributesTask.captured_trace_id = None

    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=str(uuid4()),
        job_id=str(uuid4()),
        task_identifier_name="CaptureExecutionAttributesTask",
        task_identifier_version="v0.0",
        task_input=CaptureExecutionAttributesTask()._serialize(),
        task_display="capture-trace-context",
        trace_context=traceparent.encode("utf-8"),
    )

    response = shim.execute_task(request)

    assert response.status == ExecuteTaskStatus.STATUS_COMPUTED
    assert CaptureExecutionAttributesTask.captured_trace_id is not None
    assert CaptureExecutionAttributesTask.captured_trace_id == int("4bf92f3577b34da6a3ce929d0e0e4736", 16)


def test_execute_task_ignores_invalid_trace_context(caplog: pytest.LogCaptureFixture) -> None:
    shim = PythonWorkerShim(tasks=[CaptureExecutionAttributesTask])
    worker_instance_id = _started_worker(shim)

    caplog.set_level("DEBUG", logger="tilebox.workflows.runner.worker_rpc_v1")
    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=str(uuid4()),
        job_id=str(uuid4()),
        task_identifier_name="CaptureExecutionAttributesTask",
        task_identifier_version="v0.0",
        task_input=CaptureExecutionAttributesTask()._serialize(),
        task_display="capture-invalid-trace-context",
        trace_context=b"not-a-valid-traceparent",
    )

    response = shim.execute_task(request)

    assert response.status == ExecuteTaskStatus.STATUS_COMPUTED
    assert any("invalid traceparent" in record.message for record in caplog.records)


def test_execute_task_scopes_cache_by_job_id_even_if_trace_context_changes() -> None:
    shim = PythonWorkerShim(tasks=[CacheWriteTask, CacheReadTask])
    worker_instance_id = _started_worker(shim)
    job_id = str(uuid4())

    writer_response = shim.execute_task(
        ExecuteTaskRequest(
            worker_instance_id=worker_instance_id,
            task_id=str(uuid4()),
            job_id=job_id,
            task_identifier_name="CacheWriteTask",
            task_identifier_version="v0.0",
            task_input=CacheWriteTask(key="shared", value="value-1")._serialize(),
            task_display="cache-write",
            trace_context=b"00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
        )
    )
    assert writer_response.status == ExecuteTaskStatus.STATUS_COMPUTED

    reader_response = shim.execute_task(
        ExecuteTaskRequest(
            worker_instance_id=worker_instance_id,
            task_id=str(uuid4()),
            job_id=job_id,
            task_identifier_name="CacheReadTask",
            task_identifier_version="v0.0",
            task_input=CacheReadTask(key="shared", expected_value="value-1")._serialize(),
            task_display="cache-read",
            trace_context=b"00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01",
        )
    )

    assert reader_response.status == ExecuteTaskStatus.STATUS_COMPUTED


def test_execute_task_isolates_cache_between_jobs_even_if_trace_context_matches() -> None:
    shim = PythonWorkerShim(tasks=[CacheWriteTask, CacheMissingKeyTask])
    worker_instance_id = _started_worker(shim)
    shared_trace_context = b"00-11111111111111111111111111111111-2222222222222222-01"

    writer_response = shim.execute_task(
        ExecuteTaskRequest(
            worker_instance_id=worker_instance_id,
            task_id=str(uuid4()),
            job_id=str(uuid4()),
            task_identifier_name="CacheWriteTask",
            task_identifier_version="v0.0",
            task_input=CacheWriteTask(key="shared", value="value-1")._serialize(),
            task_display="cache-write",
            trace_context=shared_trace_context,
        )
    )
    assert writer_response.status == ExecuteTaskStatus.STATUS_COMPUTED

    missing_response = shim.execute_task(
        ExecuteTaskRequest(
            worker_instance_id=worker_instance_id,
            task_id=str(uuid4()),
            job_id=str(uuid4()),
            task_identifier_name="CacheMissingKeyTask",
            task_identifier_version="v0.0",
            task_input=CacheMissingKeyTask(key="shared")._serialize(),
            task_display="cache-missing",
            trace_context=shared_trace_context,
        )
    )

    assert missing_response.status == ExecuteTaskStatus.STATUS_FAILED
    assert "KeyError" in missing_response.error_message


def test_cancel_task_marks_running_execution_as_canceled() -> None:
    shim = PythonWorkerShim(tasks=[CooperativeCancelTask])
    worker_instance_id = _started_worker(shim)
    task_id = str(uuid4())

    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=task_id,
        job_id=str(uuid4()),
        task_identifier_name="CooperativeCancelTask",
        task_identifier_version="v0.0",
        task_input=CooperativeCancelTask()._serialize(),
        task_display="cancel-me",
    )

    result_holder: list = []

    def _execute() -> None:
        result_holder.append(shim.execute_task(request))

    execution_thread = threading.Thread(target=_execute)
    execution_thread.start()

    accepted = False
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline and not accepted:
        accepted = shim.cancel_task(
            CancelTaskRequest(worker_instance_id=worker_instance_id, task_id=task_id, reason="test-cancel")
        ).accepted
        if not accepted:
            time.sleep(0.01)

    assert accepted is True

    execution_thread.join(timeout=2)
    assert not execution_thread.is_alive()
    assert len(result_holder) == 1
    assert result_holder[0].status == ExecuteTaskStatus.STATUS_CANCELED
    assert result_holder[0].was_workflow_error is False


def test_shutdown_cancels_inflight_and_refuses_new_task() -> None:
    shim = PythonWorkerShim(tasks=[CooperativeCancelTask])
    worker_instance_id = _started_worker(shim)
    task_id = str(uuid4())

    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=task_id,
        job_id=str(uuid4()),
        task_identifier_name="CooperativeCancelTask",
        task_identifier_version="v0.0",
        task_input=CooperativeCancelTask()._serialize(),
        task_display="shutdown-me",
    )

    result_holder: list = []

    def _execute() -> None:
        result_holder.append(shim.execute_task(request))

    execution_thread = threading.Thread(target=_execute)
    execution_thread.start()

    # Let the task start first, then request shutdown.
    time.sleep(0.05)
    assert shim.request_shutdown("test-shutdown") is True

    execution_thread.join(timeout=2)
    assert len(result_holder) == 1
    assert result_holder[0].status == ExecuteTaskStatus.STATUS_CANCELED

    follow_up = shim.execute_task(
        ExecuteTaskRequest(
            worker_instance_id=worker_instance_id,
            task_id=str(uuid4()),
            job_id=str(uuid4()),
            task_identifier_name="CooperativeCancelTask",
            task_identifier_version="v0.0",
            task_input=CooperativeCancelTask()._serialize(),
            task_display="new-task",
        )
    )
    assert follow_up.status == ExecuteTaskStatus.STATUS_CANCELED
