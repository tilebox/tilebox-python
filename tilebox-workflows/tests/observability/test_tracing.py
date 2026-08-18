from collections.abc import Iterator

import pytest
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, TracerProvider
from opentelemetry.sdk.trace.export import SpanProcessor

from tilebox.workflows.observability import tracing


class RecordingSpanProcessor(SpanProcessor):
    def __init__(self) -> None:
        self.span_names: list[str] = []
        self.span_attributes: dict[str, dict[str, object]] = {}

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        pass

    def on_end(self, span: ReadableSpan) -> None:
        self.span_names.append(span.name)
        self.span_attributes[span.name] = dict(span.attributes or {})

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True


@pytest.fixture(autouse=True)
def reset_tilebox_tracing() -> Iterator[None]:
    tracing._set_tilebox_tracer_provider(TracerProvider())
    tracing._workflow_tracers.clear()
    yield
    tracing._set_tilebox_tracer_provider(TracerProvider())
    tracing._workflow_tracers.clear()


@pytest.fixture
def span_processors(monkeypatch: pytest.MonkeyPatch) -> list[RecordingSpanProcessor]:
    processors: list[RecordingSpanProcessor] = []

    def create_processor(*args: object, **kwargs: object) -> RecordingSpanProcessor:  # noqa: ARG001
        processor = RecordingSpanProcessor()
        processors.append(processor)
        return processor

    monkeypatch.setattr(tracing, "_otel_span_exporter", create_processor)
    return processors


def test_workflow_tracers_do_not_share_client_span_processors(
    span_processors: list[RecordingSpanProcessor],
) -> None:
    tracers = [tracing.WorkflowTracer(service=None, url="https://api.tilebox.com", token=None) for _ in range(3)]

    for index, tracer in enumerate(tracers):
        with tracer.span(f"span-{index}"):
            pass

    assert [processor.span_names for processor in span_processors] == [["span-0"], ["span-1"], ["span-2"]]


def test_workflow_tracers_copy_configured_span_processors_once(
    span_processors: list[RecordingSpanProcessor],
) -> None:
    tracing.configure_otel_tracing(endpoint="https://otel.example.com")
    tracers = [tracing.WorkflowTracer(service=None, url="https://api.tilebox.com", token=None) for _ in range(2)]

    for index, tracer in enumerate(tracers):
        with tracer.span(f"span-{index}"):
            pass

    assert [processor.span_names for processor in span_processors] == [
        ["span-0", "span-1"],
        ["span-0"],
        ["span-1"],
    ]


def test_workflow_tracer_propagates_task_id_to_sub_spans(
    span_processors: list[RecordingSpanProcessor],
) -> None:
    tracer = tracing.WorkflowTracer(service=None, url="https://api.tilebox.com", token=None)

    with tracer.span("task") as task_span:
        task_span.set_attribute("task_id", "task-123")
        with tracer.span("sub-span"), tracer.span("nested-sub-span"):
            pass

    assert span_processors[0].span_attributes == {
        "nested-sub-span": {"task_id": "task-123"},
        "sub-span": {"task_id": "task-123"},
        "task": {"task_id": "task-123"},
    }
