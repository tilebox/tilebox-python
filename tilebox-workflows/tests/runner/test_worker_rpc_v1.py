import threading
import time
from typing import ClassVar
from uuid import uuid4

import pytest
from opentelemetry.trace import get_current_span

from tilebox.workflows import ExecutionContext, Task
from tilebox.workflows.observability.execution_attributes import current_execution_attributes_dict
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
    captured_attributes: ClassVar[dict[str, str]] = {}
    captured_trace_id: ClassVar[int | None] = None

    def execute(self, context: ExecutionContext) -> None:
        _ = context
        CaptureExecutionAttributesTask.captured_attributes = current_execution_attributes_dict().copy()
        CaptureExecutionAttributesTask.captured_trace_id = get_current_span().get_span_context().trace_id


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
        task_identifier_name="FailingTask",
        task_identifier_version="v0.0",
        task_input=FailingTask()._serialize(),
        task_display="failing-task",
    )

    response = shim.execute_task(request)

    assert response.status == ExecuteTaskStatus.STATUS_FAILED
    assert response.was_workflow_error is True
    assert "boom" in response.error_message


def test_execute_task_binds_execution_attributes() -> None:
    shim = PythonWorkerShim(tasks=[CaptureExecutionAttributesTask])
    worker_instance_id = _started_worker(shim)

    CaptureExecutionAttributesTask.captured_attributes = {}
    CaptureExecutionAttributesTask.captured_trace_id = None

    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=str(uuid4()),
        job_id=str(uuid4()),
        task_identifier_name="CaptureExecutionAttributesTask",
        task_identifier_version="v0.0",
        task_input=CaptureExecutionAttributesTask()._serialize(),
        task_display="capture-execution-attributes",
    )

    response = shim.execute_task(request)

    assert response.status == ExecuteTaskStatus.STATUS_COMPUTED
    assert CaptureExecutionAttributesTask.captured_attributes == {
        "job.id": request.job_id,
        "tilebox.job_id": request.job_id,
        "task.id": request.task_id,
        "tilebox.task_id": request.task_id,
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


def test_cancel_task_marks_running_execution_as_canceled() -> None:
    shim = PythonWorkerShim(tasks=[CooperativeCancelTask])
    worker_instance_id = _started_worker(shim)
    task_id = str(uuid4())

    request = ExecuteTaskRequest(
        worker_instance_id=worker_instance_id,
        task_id=task_id,
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
            task_identifier_name="CooperativeCancelTask",
            task_identifier_version="v0.0",
            task_input=CooperativeCancelTask()._serialize(),
            task_display="new-task",
        )
    )
    assert follow_up.status == ExecuteTaskStatus.STATUS_CANCELED
