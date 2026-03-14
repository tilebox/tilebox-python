from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from opentelemetry.trace import Span


@dataclass(frozen=True)
class ExecutionAttributes:
    job_id: str | None = None
    task_id: str | None = None

    def to_otel_attributes(self) -> dict[str, str]:
        attributes: dict[str, str] = {}
        if self.job_id:
            attributes["job.id"] = self.job_id
            attributes["tilebox.job_id"] = self.job_id
        if self.task_id:
            attributes["task.id"] = self.task_id
            attributes["tilebox.task_id"] = self.task_id
        return attributes


_execution_attributes = ContextVar[ExecutionAttributes | None](
    "tilebox_workflows_execution_attributes",
    default=None,
)


@contextmanager
def bind_execution_attributes(job_id: str | None = None, task_id: str | None = None) -> Iterator[None]:
    current = current_execution_attributes()
    resolved = ExecutionAttributes(
        job_id=current.job_id if job_id is None else job_id,
        task_id=current.task_id if task_id is None else task_id,
    )
    token = _execution_attributes.set(resolved)
    try:
        yield
    finally:
        _execution_attributes.reset(token)


def current_execution_attributes() -> ExecutionAttributes:
    attributes = _execution_attributes.get()
    if attributes is None:
        return ExecutionAttributes()
    return attributes


def current_execution_attributes_dict() -> dict[str, str]:
    return current_execution_attributes().to_otel_attributes()


def set_span_execution_attributes(span: Span, *, job_id: str | None = None, task_id: str | None = None) -> None:
    for key, value in ExecutionAttributes(job_id=job_id, task_id=task_id).to_otel_attributes().items():
        span.set_attribute(key, value)
