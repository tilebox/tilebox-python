import logging
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tilebox.workflows.cache import InMemoryCache
from tilebox.workflows.data import ExecutionStats, Job, JobState, RunnerContext, Task, TaskIdentifier
from tilebox.workflows.observability import tracing
from tilebox.workflows.observability.execution_attributes import (
    bind_execution_attributes,
    current_execution_attributes_dict,
)
from tilebox.workflows.observability.logging import OTELLoggingHandler
from tilebox.workflows.runner.task_runner import TaskRunner


def test_bind_execution_attributes_resets_after_scope() -> None:
    assert current_execution_attributes_dict() == {}

    with bind_execution_attributes(job_id="job-123", task_id="task-456"):
        assert current_execution_attributes_dict() == {
            "job.id": "job-123",
            "tilebox.job_id": "job-123",
            "task.id": "task-456",
            "tilebox.task_id": "task-456",
        }

    assert current_execution_attributes_dict() == {}


def test_logging_handler_includes_execution_and_exception_attributes() -> None:
    try:
        _raise_value_error()
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=42,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )

    with bind_execution_attributes(job_id="job-abc", task_id="task-def"):
        attributes = OTELLoggingHandler._get_attributes(record)

    assert attributes["job.id"] == "job-abc"
    assert attributes["tilebox.job_id"] == "job-abc"
    assert attributes["task.id"] == "task-def"
    assert attributes["tilebox.task_id"] == "task-def"
    assert attributes["exception.type"] == "ValueError"
    assert attributes["exception.message"] == "boom"


def test_start_job_span_sets_job_attributes() -> None:
    original_provider = tracing._get_tilebox_tracer_provider()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracing._set_tilebox_tracer_provider(provider)

    try:
        tracer = tracing.WorkflowTracer()
        job = _job()

        with tracer.start_job_span(job, "test-job-span"):
            assert current_execution_attributes_dict()["job.id"] == str(job.id)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["job.id"] == str(job.id)
        assert spans[0].attributes["tilebox.job_id"] == str(job.id)
    finally:
        tracing._set_tilebox_tracer_provider(original_provider)


def test_task_runner_failure_logs_include_execution_attributes() -> None:
    captured_attributes: list[dict[str, str]] = []

    class CaptureAttributesHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno >= logging.ERROR:
                captured_attributes.append(current_execution_attributes_dict().copy())

    logger = logging.getLogger("tilebox.workflows.tests.runner.failure")
    previous_handlers = list(logger.handlers)
    previous_propagate = logger.propagate

    handler = CaptureAttributesHandler(level=logging.ERROR)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    try:
        task_service = MagicMock()
        lease_renewer = MagicMock()
        runner = TaskRunner(
            service=task_service,
            cluster="test-cluster",
            cache=InMemoryCache(),
            tracer=None,
            logger=logger,
            lease_renewer=lease_renewer,
            context=RunnerContext(),
        )

        job = _job()
        task_id = uuid4()
        task = Task(
            id=task_id,
            identifier=TaskIdentifier(name="tilebox.com/test/failure", version="v0.0"),
            job=job,
        )

        shutdown_context = MagicMock()
        shutdown_context.stop_if_shutting_down.return_value = lambda _: False

        with patch.object(runner, "_try_execute", side_effect=ValueError("oh no")):
            result = runner._execute(task, shutdown_context)

        assert result is None
        task_service.task_failed.assert_called_once()
        assert captured_attributes[-1] == {
            "job.id": str(job.id),
            "tilebox.job_id": str(job.id),
            "task.id": str(task_id),
            "tilebox.task_id": str(task_id),
        }
    finally:
        logger.handlers = previous_handlers
        logger.propagate = previous_propagate


def _job() -> Job:
    return Job(
        id=uuid4(),
        name="test-job",
        trace_parent="00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
        state=JobState.RUNNING,
        submitted_at=datetime.now(tz=timezone.utc),
        progress=[],
        execution_stats=ExecutionStats(
            first_task_started_at=None,
            last_task_stopped_at=None,
            compute_time=timedelta(seconds=0),
            elapsed_time=timedelta(seconds=0),
            parallelism=1.0,
            total_tasks=0,
            tasks_by_state={},
        ),
    )


def _raise_value_error() -> None:
    raise ValueError("boom")
