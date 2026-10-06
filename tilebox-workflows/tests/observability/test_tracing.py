import json
import os
import subprocess
import sys
from collections.abc import Iterator
from importlib.metadata import version
from unittest.mock import patch

import pytest
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tilebox.workflows.observability import logging as observability_logging
from tilebox.workflows.observability import tracing


@pytest.mark.parametrize("from_environment", [False, True])
@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("https://collector.example", "https://collector.example/v1/traces"),
        ("https://collector.example/tenant", "https://collector.example/tenant/v1/traces"),
        ("https://collector.example/tenant/", "https://collector.example/tenant/v1/traces"),
        ("https://collector.example/tenant/v1/traces", "https://collector.example/tenant/v1/traces"),
    ],
)
def test_otel_span_exporter_endpoint(
    monkeypatch: pytest.MonkeyPatch, endpoint: str, expected: str, from_environment: bool
) -> None:
    monkeypatch.setenv("OTEL_TRACES_ENDPOINT", endpoint if from_environment else "https://ignored.example")
    headers = {"Authorization": "Bearer test-key"}
    with patch.object(tracing, "OTLPSpanExporter", return_value=InMemorySpanExporter()) as factory:
        processor = tracing._otel_span_exporter(None if from_environment else endpoint, headers=headers)
        try:
            factory.assert_called_once_with(endpoint=expected, headers=headers)
        finally:
            processor.shutdown()


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
    original_provider = tracing._get_tilebox_tracer_provider()
    tracing._workflow_tracers.clear()
    tracing._set_tilebox_tracer_provider(TracerProvider(resource=observability_logging._get_default_resource()))
    yield
    tracing._workflow_tracers.clear()
    tracing._set_tilebox_tracer_provider(original_provider)


@pytest.fixture
def span_processors(monkeypatch: pytest.MonkeyPatch) -> list[RecordingSpanProcessor]:
    processors: list[RecordingSpanProcessor] = []

    def create_processor(*args: object, **kwargs: object) -> RecordingSpanProcessor:  # noqa: ARG001
        processor = RecordingSpanProcessor()
        processors.append(processor)
        return processor

    monkeypatch.setattr(tracing, "_otel_span_exporter", create_processor)
    return processors


@pytest.mark.parametrize("otel_service_name", ["unknown_service:python", "unknown_service:python.exe", "other-default"])
def test_exported_traces_use_tilebox_resource_defaults(otel_service_name: str) -> None:
    # Exercise actual module initialization, independent of OTEL's platform-specific defaults.
    instance_id = "66d615f3-7d53-4a31-bc94-94cbb9d9ffa2"
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("TILEBOX_", "OTEL_"))}
    environment.update(
        TILEBOX_RUNTIME_ID=instance_id,
        OTEL_SERVICE_NAME=otel_service_name,
        OTEL_RESOURCE_ATTRIBUTES="service.instance.id=otel-generated",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from unittest.mock import patch
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from tilebox.workflows.observability import tracing
from tilebox.workflows.observability.logging import _get_default_resource

exporter = InMemorySpanExporter()
with patch.object(tracing, "_otel_span_exporter", return_value=SimpleSpanProcessor(exporter)):
    tracer = tracing.WorkflowTracer(service=None, url="https://api.tilebox.com", token=None)
    with tracer.span("task"):
        pass
[span] = exporter.get_finished_spans()
print(json.dumps([dict(span.resource.attributes), dict(_get_default_resource().attributes)]))
""",
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    expected = {
        "service.name": "tilebox-python",
        "service.namespace": "tilebox.workflows",
        "service.version": version("tilebox-workflows"),
        "service.instance.id": instance_id,
    }
    trace_resource, log_resource = json.loads(result.stdout)
    assert {key: trace_resource.get(key) for key in expected} == expected
    assert {key: log_resource.get(key) for key in expected} == expected


@pytest.mark.parametrize("service_name", [None, "custom-worker", "unknown_service:python.exe"])
@pytest.mark.parametrize("explicit_resource", [False, True])
def test_exported_traces_preserve_configured_resources(service_name: str | None, explicit_resource: bool) -> None:
    attributes = {"service.instance.id": "custom-instance", "deployment": "test"}
    if service_name is not None:
        attributes["service.name"] = service_name
    resource = Resource(attributes, schema_url="https://example.com/schema")
    if not explicit_resource:
        tracing._set_tilebox_tracer_provider(TracerProvider(resource=resource))
    exporter = InMemorySpanExporter()
    with patch.object(tracing, "_otel_span_exporter", return_value=SimpleSpanProcessor(exporter)):
        tracer = tracing.WorkflowTracer(
            service=resource if explicit_resource else None, url="https://api.tilebox.com", token=None
        )
        with tracer.span("task"):
            pass

    [span] = exporter.get_finished_spans()
    for result in (span.resource, observability_logging._get_default_resource(resource)):
        assert {key: result.attributes.get(key) for key in attributes} == attributes
        assert result.attributes["service.name"] == (service_name or "tilebox-python")
        assert result.attributes["service.namespace"] == "tilebox.workflows"
        assert result.attributes["service.version"] == version("tilebox-workflows")
        assert result.schema_url == resource.schema_url


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


def test_adding_external_exports_after_client_preserves_api_export(
    span_processors: list[RecordingSpanProcessor],
) -> None:
    tracer = tracing.WorkflowTracer(service=None, url="https://api.tilebox.com", token=None)
    with tracer.span("before"):
        pass
    tracing.configure_otel_tracing(service="first", endpoint="https://first.example")
    with tracer.span("after-first"):
        pass
    tracing.configure_otel_tracing(service="second", endpoint="https://second.example")
    with tracer.span("after-second"):
        pass
    assert [processor.span_names for processor in span_processors] == [
        ["before", "after-first", "after-second"],
        ["after-first", "after-second"],
        ["after-second"],
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
