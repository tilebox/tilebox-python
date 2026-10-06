import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import msgspec
import pytest
from affine import Affine
from opentelemetry._logs import SeverityNumber
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.trace import Span, TracerProvider

from tilebox.workflows._codec import registry
from tilebox.workflows.observability import _logging as structured_logging
from tilebox.workflows.observability import logging as observability
from tilebox.workflows.observability import tracing
from tilebox.workflows.observability._log_stream import _LogQueue, _OTLPQueueHandler
from tilebox.workflows.observability._logging import StructuredLogger, internal_logger, logger, root_logger, task_logger


@pytest.fixture
def isolated_logging(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    # Reset process-wide handlers, initialization state, and thresholds so each test
    # configures its own outputs. monkeypatch and caplog restore prior state afterward.
    monkeypatch.setattr(root_logger, "handlers", [])
    monkeypatch.setattr(observability, "_api_handler", None)
    monkeypatch.setattr(observability, "_console_handlers", [])
    monkeypatch.setattr(observability, "_console_configured", False)
    monkeypatch.setattr(observability, "managed_log_queue", None)
    caplog.set_level(logging.INFO, logger=task_logger.name)
    caplog.set_level(logging.ERROR, logger=internal_logger.name)


@pytest.mark.parametrize("from_environment", [False, True])
@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("https://collector.example", "https://collector.example/v1/logs"),
        ("https://collector.example/tenant", "https://collector.example/tenant/v1/logs"),
        ("https://collector.example/tenant/", "https://collector.example/tenant/v1/logs"),
        ("https://collector.example/tenant/v1/logs", "https://collector.example/tenant/v1/logs"),
    ],
)
def test_otel_log_exporter_endpoint(
    monkeypatch: pytest.MonkeyPatch, endpoint: str, expected: str, from_environment: bool
) -> None:
    monkeypatch.setenv("OTEL_LOGS_ENDPOINT", endpoint if from_environment else "https://ignored.example")
    headers = {"Authorization": "Bearer test-key"}
    with patch.object(observability, "OTLPLogExporter", return_value=InMemoryLogRecordExporter()) as factory:
        processor = observability._otel_log_exporter(None if from_environment else endpoint, headers=headers)
        try:
            factory.assert_called_once_with(endpoint=expected, headers=headers)
        finally:
            processor.shutdown()


@pytest.mark.parametrize("formatted", [False, True])
@pytest.mark.parametrize(
    ("level", "severity", "text"),
    [(logging.WARNING, SeverityNumber.WARN, "WARN"), (logging.CRITICAL, SeverityNumber.FATAL, "FATAL")],
)
def test_otel_handler_preserves_record_fields(formatted: bool, level: int, severity: SeverityNumber, text: str) -> None:
    exporter = InMemoryLogRecordExporter()
    provider = observability.LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    handler = observability.OTELLoggingHandler(logger_provider=provider)
    if formatted:
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    record = logging.LogRecord("task.example", level, "workflow.py", 42, "task %s", ("started",), None)
    record.created = 1234.5
    try:
        handler.handle(record)
        (exported,) = exporter.get_finished_logs()
        assert exported.instrumentation_scope is not None
        assert exported.instrumentation_scope.name == "task.example"
        assert exported.log_record.timestamp == 1_234_500_000_000
        assert exported.log_record.observed_timestamp is not None
        assert exported.log_record.severity_number == severity
        assert exported.log_record.severity_text == text
        assert exported.log_record.body == ("task.example: task started" if formatted else "task started")
        assert not exported.log_record.attributes
    finally:
        provider.shutdown()


def test_otel_handler_suppresses_recursive_exports() -> None:
    handler = observability.OTELLoggingHandler(logger_provider=observability.LoggerProvider())
    record = logging.LogRecord("task.example", logging.INFO, __file__, 0, "outer", (), None)
    recursive_record = logging.LogRecord("task.example", logging.WARNING, __file__, 0, "exporter diagnostic", (), None)
    with patch.object(observability, "get_otel_logger") as get_logger:
        emit = get_logger.return_value.emit
        emit.side_effect = lambda _: handler.emit(recursive_record)
        handler.emit(record)
        handler.emit(record)
        assert [call.args[0].body for call in emit.call_args_list] == ["outer", "outer"]


@pytest.mark.usefixtures("isolated_logging")
@pytest.mark.parametrize(
    ("task_level", "internal_level"), [(logging.DEBUG, logging.ERROR), (logging.ERROR, logging.DEBUG)]
)
def test_one_exporter_with_independent_logger_levels(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str], task_level: int, internal_level: int
) -> None:
    caplog.set_level(task_level, logger=task_logger.name)
    caplog.set_level(internal_level, logger=internal_logger.name)
    exporter = InMemoryLogRecordExporter()
    with patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(exporter)) as factory:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: observability.initialize_logging("https://first.example", "first-key"), range(12)))
        handler = observability._api_handler
        observability.initialize_logging("https://other.example", "other-key")
    factory.assert_called_once_with(endpoint="https://first.example", headers={"Authorization": "Bearer first-key"})
    assert observability._api_handler is handler
    assert handler is not None
    assert handler.level == logging.NOTSET
    assert sum(isinstance(item, observability.OTELLoggingHandler) for item in root_logger.handlers) == 1
    assert not task_logger.handlers
    assert not internal_logger.handlers

    for severity in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
        StructuredLogger(task_logger).log(severity, f"task-{severity}")
        logger.log(severity, f"internal-{severity}")
    expected = (
        ["task-10", "task-20", "task-30", "task-40", "internal-40"]
        if task_level == logging.DEBUG
        else ["internal-10", "internal-20", "internal-30", "task-40", "internal-40"]
    )
    assert [item.log_record.body for item in exporter.get_finished_logs()] == expected
    assert [line.split(": ", 2)[2] for line in capsys.readouterr().out.splitlines()] == expected


@pytest.mark.usefixtures("isolated_logging")
def test_both_loggers_preserve_attributes_with_and_without_a_span() -> None:
    exporter = InMemoryLogRecordExporter()
    with patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(exporter)):
        observability.initialize_logging("https://example.test", "test-key")
    tracer_provider = TracerProvider()
    for target in (StructuredLogger(task_logger), logger):
        target.error("no-context")
        target.bind(task_id="supplied-task").error(
            "supplied-context", trace_id="supplied-trace", span_id="supplied-span"
        )
        with tracer_provider.get_tracer(__name__).start_as_current_span("task") as span:
            target.bind(task_id="task-123").error("with-context", attempt=3)
            span_context = span.get_span_context()
        plain, supplied, correlated = [item.log_record for item in exporter.get_finished_logs()][-3:]
        assert not plain.trace_id
        assert not plain.span_id
        assert not plain.attributes
        assert supplied.attributes == {
            "task_id": "supplied-task",
            "trace_id": "supplied-trace",
            "span_id": "supplied-span",
        }
        assert correlated.trace_id == span_context.trace_id
        assert correlated.span_id == span_context.span_id
        assert correlated.attributes == {
            "task_id": "task-123",
            "attempt": 3,
            "trace_id": f"{span_context.trace_id:032x}",
            "span_id": f"{span_context.span_id:016x}",
        }
    tracer_provider.shutdown()


@pytest.mark.parametrize("structured", [False, True])
def test_export_attributes_capture_context_once_without_mutating_record(structured: bool) -> None:
    metadata = {"task_id": "task-123", "details": {"attempt": 2}}
    record = logging.makeLogRecord({"msg": "failed", "exc_info": (ValueError, ValueError({"reason": "bad"}), None)})
    if structured:
        record.tilebox_structured_log_attributes = metadata
    handler = observability.OTELLoggingHandler(logger_provider=observability.LoggerProvider())
    with patch.object(structured_logging, "_current_span_attributes", return_value={"trace_id": "fallback"}) as context:
        attributes = handler._get_attributes(record)
    assert context.call_count == (0 if structured else 1)
    assert attributes == {
        **({"task_id": "task-123", "details": '{"attempt":2}'} if structured else {"trace_id": "fallback"}),
        "exception.type": "ValueError",
        "exception.message": '{"reason":"bad"}',
    }
    assert metadata == {"task_id": "task-123", "details": {"attempt": 2}}


@pytest.mark.parametrize("stdlib", [False, True])
@pytest.mark.parametrize("stream_first", [False, True])
def test_codecs_run_once_per_record_across_handlers(stdlib: bool, stream_first: bool) -> None:
    codec = registry.find(Affine)
    assert codec is not None
    encode = MagicMock(wraps=codec.encode)
    target = logging.Logger("normalized-records", logging.INFO)  # noqa: LOG001 -- isolated from process-wide loggers
    queue = _LogQueue()
    exporters = [InMemoryLogRecordExporter(), InMemoryLogRecordExporter()]
    providers = [observability.LoggerProvider() for _ in exporters]
    handlers: list[logging.Handler] = [_OTLPQueueHandler(queue), tracing.SpanEventLoggingHandler()]
    for provider, exporter in zip(providers, exporters, strict=True):
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
        handlers.append(observability.OTELLoggingHandler(logger_provider=provider))
    for handler in handlers if stream_first else reversed(handlers):
        target.addHandler(handler)
    tracer_provider = TracerProvider()
    value = {"transform": Affine(2, 3, 5, 7, 11, 13)}
    facade = StructuredLogger(target).bind(input=value)
    try:
        with patch.dict(registry._cache, {Affine: replace(codec, encode=encode)}):
            facade.debug("filtered")
            encode.assert_not_called()
            with tracer_provider.get_tracer(__name__).start_as_current_span("task") as span:
                assert isinstance(span, Span)
                for index in range(2):
                    if stdlib:
                        target.info("record-%s", index, extra={"tilebox_structured_log_attributes": {"input": value}})
                    else:
                        facade.info("record-%s", index)
                    assert encode.call_count == index + 1
                assert len(span.events) == 2
                for event in span.events:
                    assert event.attributes is not None
                    assert event.attributes["input"] == '{"transform":[2.0,3.0,5.0,7.0,11.0,13.0]}'
        # Records hold snapshots, not references to task-owned mutable containers.
        value.clear()
        queue.seal()
        stream_records = list(queue.subscribe())
        assert [record.body.string_value for record in stream_records] == ["record-0", "record-1"]
        for record in stream_records:
            attributes = {item.key: item.value for item in record.attributes}
            transform = attributes["input"].kvlist_value.values[0]
            assert transform.key == "transform"
            assert [item.double_value for item in transform.value.array_value.values] == [2, 3, 5, 7, 11, 13]
        for exporter in exporters:
            records = [item.log_record for item in exporter.get_finished_logs()]
            assert [record.body for record in records] == ["record-0", "record-1"]
            for record in records:
                assert record.attributes is not None
                assert record.attributes["input"] == '{"transform":[2.0,3.0,5.0,7.0,11.0,13.0]}'
    finally:
        tracer_provider.shutdown()
        for provider in providers:
            provider.shutdown()


@pytest.mark.usefixtures("isolated_logging")
@pytest.mark.parametrize("external_first", [False, True])
def test_external_exports_and_console_do_not_replace_api_or_stream(external_first: bool) -> None:
    queue = _LogQueue()
    root_logger.addHandler(_OTLPQueueHandler(queue))
    api, external = InMemoryLogRecordExporter(), InMemoryLogRecordExporter()
    first, second = StringIO(), StringIO()
    with patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(external)):
        if external_first:
            observability.configure_otel_logging(endpoint="https://external.example")
            observability.configure_console_logging(stream=first)
    with patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(api)):
        observability.initialize_logging("https://api.tilebox.com", "test-key")
    with patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(external)):
        if not external_first:
            observability.configure_otel_logging(endpoint="https://external.example")
            observability.configure_console_logging(stream=first)
    observability.configure_console_logging(stream=second, reconfigure=False)
    observability.configure_log_level(logging.DEBUG)
    assert internal_logger.level == logging.ERROR
    task_logger.info("all outputs")
    observability.configure_console_logging(enabled=False)
    observability.initialize_logging("https://ignored.example", "ignored-key")
    task_logger.debug("exports only")
    assert first.getvalue().count("all outputs") == second.getvalue().count("all outputs") == 1
    assert "exports only" not in first.getvalue() + second.getvalue()
    for exporter in (api, external):
        assert [item.log_record.body for item in exporter.get_finished_logs()] == ["all outputs", "exports only"]
    queue.seal()
    assert [record.body.string_value for record in queue.subscribe()] == ["all outputs", "exports only"]


@pytest.mark.usefixtures("isolated_logging")
@pytest.mark.parametrize("tilebox_debug", [False, True])
def test_log_level_override_filters_tasks_and_diagnostics_independently(
    caplog: pytest.LogCaptureFixture, tilebox_debug: bool
) -> None:
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger=internal_logger.name)
    observability.configure_log_level(logging.ERROR, tilebox_debug=tilebox_debug)
    StructuredLogger(task_logger).debug("task-debug")
    logger.debug("sdk-debug")
    StructuredLogger(task_logger).error("task-error")
    assert [record.message for record in caplog.records] == (
        ["sdk-debug", "task-error"] if tilebox_debug else ["task-error"]
    )


@pytest.mark.usefixtures("isolated_logging")
def test_log_level_override_defaults_reset_both_levels() -> None:
    observability.configure_log_level(logging.CRITICAL, tilebox_debug=True)
    observability.configure_log_level()
    assert task_logger.level == logging.INFO
    assert internal_logger.level == logging.ERROR


@pytest.mark.usefixtures("isolated_logging")
def test_task_values_and_unserializable_attributes_reach_both_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    @dataclass
    class Input:
        transform: Affine
        path: Path
        secret: str = field(default="hidden", metadata={"skip_serialization": True})

    class Broken:
        def __str__(self) -> str:
            raise ValueError("broken string conversion")

    cyclic: list[Any] = []
    cyclic.append(cyclic)
    queue = _LogQueue()
    monkeypatch.setattr(observability, "managed_log_queue", queue)
    root_logger.addHandler(_OTLPQueueHandler(queue))
    exporter = InMemoryLogRecordExporter()
    with patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(exporter)):
        observability.initialize_logging("https://api.tilebox.com", "test-key")
    StructuredLogger(task_logger).info(
        "input",
        input=Input(Affine(2, 3, 5, 7, 11, 13), Path("image.tif")),
        counts={date(2026, 9, 16): 3},
        cyclic=cyclic,
        unsupported=Broken(),
    )
    queue.seal()
    [record] = queue.subscribe()
    stream_attributes = {item.key: item.value for item in record.attributes}
    input_attributes = {item.key: item.value for item in stream_attributes["input"].kvlist_value.values}
    assert [item.double_value for item in input_attributes["transform"].array_value.values] == [2, 3, 5, 7, 11, 13]
    assert input_attributes["path"].string_value == "image.tif"
    counts = stream_attributes["counts"].kvlist_value.values
    assert len(counts) == 1
    assert counts[0].key == "2026-09-16"
    assert counts[0].value.int_value == 3
    assert stream_attributes["cyclic"].string_value == "[[...]]"
    assert stream_attributes["unsupported"].string_value == "<unserializable Broken>"
    attributes = exporter.get_finished_logs()[0].log_record.attributes
    assert attributes is not None
    assert isinstance(attributes["input"], str)
    assert isinstance(attributes["counts"], str)
    assert msgspec.json.decode(attributes["input"]) == {
        "transform": [2, 3, 5, 7, 11, 13],
        "path": "image.tif",
    }
    assert msgspec.json.decode(attributes["counts"]) == {"2026-09-16": 3}
    assert attributes["cyclic"] == "[[...]]"
    assert attributes["unsupported"] == "<unserializable Broken>"


@pytest.mark.parametrize("without_otel", [False, True])
def test_facade_works_without_otel_or_tracer(without_otel: bool) -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("TILEBOX_")}
    script = """
import io
import logging
import sys
from tilebox.workflows.observability._logging import StructuredLogger
assert not any(name.startswith('opentelemetry') for name in sys.modules)
OUTPUT = io.StringIO()
target = logging.Logger('standalone', logging.DEBUG)
target.addHandler(logging.StreamHandler(OUTPUT))
"""
    if without_otel:
        script += "sys.modules['opentelemetry.trace'] = None\n"
    script += """
StructuredLogger(target).info('plain message', task_id='still-allowed')
assert OUTPUT.getvalue() == 'plain message\\n'
assert 'opentelemetry.sdk' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", script], env=env, check=True, capture_output=True, timeout=10)  # noqa: S603 -- fixed test script


@pytest.mark.parametrize("missing", ["TILEBOX_API_URL", "TILEBOX_API_KEY"])
def test_incomplete_environment_skips_startup_logging(missing: str) -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("TILEBOX_")}
    env.update({"TILEBOX_API_URL": "https://startup.example", "TILEBOX_API_KEY": "startup-key"})
    env.pop(missing)
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import tilebox.workflows
from tilebox.workflows.observability._logging import root_logger
assert not root_logger.handlers
assert not any(name.startswith('opentelemetry') for name in sys.modules)
""",
        ],
        env=env,
        check=True,
        capture_output=True,
        timeout=10,
    )


@pytest.mark.parametrize(
    ("level", "debug", "expected"),
    [("debug", "false", "10 40"), ("critical", "true", "50 10"), ("", "0", "20 40")],
)
def test_environment_sets_logger_thresholds(level: str, debug: str, expected: str) -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("TILEBOX_")}
    env.update({"TILEBOX_LOG_LEVEL": level, "TILEBOX_DEBUG": debug})
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from tilebox.workflows.observability._logging import task_logger, internal_logger
print(task_logger.level, internal_logger.level)
""",
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.stdout.strip() == expected
