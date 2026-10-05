import logging
import os
import subprocess
import sys
import threading
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor

from tilebox.workflows import Client, Runner
from tilebox.workflows.observability import logging as observability
from tilebox.workflows.observability._log_stream import _LogQueue, _OTLPQueueHandler
from tilebox.workflows.observability._logging import internal_logger, logger, root_logger, task_logger
from tilebox.workflows.observability.logging import _configure_runtime_logging, configure_console_logging
from tilebox.workflows.runner.worker_service import WorkerServiceServicer
from tilebox.workflows.workflows.v1 import worker_pb2


@pytest.fixture(autouse=True)
def isolated_handlers(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(root_logger, "handlers", [])
    monkeypatch.setattr(observability, "_api_handler", None)
    monkeypatch.setattr(observability, "_console_handlers", [])
    monkeypatch.setattr(observability, "_console_configured", False)
    monkeypatch.setattr(observability, "managed_log_queue", None)
    caplog.set_level(logging.INFO, logger=task_logger.name)
    caplog.set_level(logging.ERROR, logger=internal_logger.name)


def test_worker_initialization_fallback_is_idempotent() -> None:
    exporter = InMemoryLogRecordExporter()
    request = worker_pb2.InitializeRunnerRequest(
        api_connection=worker_pb2.TileboxAPIConnection(url="https://legacy.example", token="legacy-key")  # noqa: S106
    )
    with (
        patch("tilebox.workflows.client.open_channel"),
        patch("tilebox.workflows.client.WorkflowTracer"),
        patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(exporter)) as factory,
    ):
        for _ in range(2):
            service = WorkerServiceServicer(Runner(tasks=[]), lambda: None)
            service.InitializeWorker(request, MagicMock())
    factory.assert_called_once_with(endpoint="https://legacy.example", headers={"Authorization": "Bearer legacy-key"})
    logger.error("legacy-runtime")
    assert [item.log_record.body for item in exporter.get_finished_logs()] == ["legacy-runtime"]


def test_direct_runner_initializes_on_connect_not_client_creation(capsys: pytest.CaptureFixture[str]) -> None:
    exporter = InMemoryLogRecordExporter()
    with (
        patch("tilebox.workflows.client.open_channel"),
        patch("tilebox.workflows.client.WorkflowTracer"),
        patch("tilebox.workflows.client.TaskRunner"),
        patch("tilebox.workflows.client._LeaseRenewer"),
        patch.object(observability, "_otel_log_exporter", return_value=SimpleLogRecordProcessor(exporter)) as factory,
    ):
        client = Client(url="https://direct.example", token="direct-key")  # noqa: S106
        factory.assert_not_called()
        assert observability._api_handler is None
        with patch.object(client, "clusters"):
            Runner(tasks=[]).connect_to(client)
            client.runner()
    factory.assert_called_once_with(endpoint="https://direct.example", headers={"Authorization": "Bearer direct-key"})
    client._task_logger.info("direct-task")
    logger.error("direct-internal")
    expected = ["direct-task", "direct-internal"]
    assert [item.log_record.body for item in exporter.get_finished_logs()] == expected
    assert [line.split(": ", 2)[2] for line in capsys.readouterr().out.splitlines()] == expected


@pytest.mark.parametrize("mode", ["runtime", "blocked-runtime", "direct"])
def test_api_flush_and_process_exit(mode: str) -> None:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("TILEBOX_")}
    if mode != "direct":
        environment["TILEBOX_WORKER_ADDRESS"] = "127.0.0.1:0"
    result = subprocess.run(  # noqa: S603 -- interpreter, script, and mode are controlled by this test
        [
            sys.executable,
            "-c",
            """
import sys
import threading
from unittest.mock import patch
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, InMemoryLogRecordExporter
from tilebox.workflows.observability import logging as logs

mode = sys.argv[1]
started = threading.Event()

class Exporter(InMemoryLogRecordExporter):
    def export(self, batch):
        started.set()
        if mode == "blocked-runtime":
            threading.Event().wait(30)
        print("exported", flush=True)
        return super().export(batch)

exporter = Exporter()
processor = BatchLogRecordProcessor(exporter, schedule_delay_millis=60000)
with patch.object(logs, '_otel_log_exporter', return_value=processor):
    logs.initialize_logging('http://unused.example', None)
logs.get_logger().warning('queued')
if mode != "direct":
    logs.flush_api_logging(timeout_millis=100)
    assert started.wait(timeout=1)
    if mode == "runtime":
        assert [item.log_record.body for item in exporter.get_finished_logs()] == ['queued']
print("main exited", flush=True)
""",
            mode,
        ],
        env=environment,
        capture_output=True,
        text=True,
        # Also catches a second, unbounded flush from OTEL/logging exit hooks.
        timeout=10,
        check=True,
    )
    assert "main exited" in result.stdout
    assert result.stderr == ""
    if mode == "blocked-runtime":
        assert "exported" not in result.stdout
    elif mode == "direct":
        assert result.stdout.index("main exited") < result.stdout.index("exported")
    else:
        assert result.stdout.index("exported") < result.stdout.index("main exited")


def test_unmanaged_runtime_adds_one_console_handler(capsys: pytest.CaptureFixture[str]) -> None:
    handler = logging.NullHandler()
    root_logger.addHandler(handler)
    assert _configure_runtime_logging() is None
    assert _configure_runtime_logging() is None
    assert handler in root_logger.handlers
    task_logger.info("console message")
    assert capsys.readouterr().out.endswith(": INFO: console message\n")


def test_existing_console_is_reused(capsys: pytest.CaptureFixture[str]) -> None:
    output = StringIO()
    configure_console_logging(stream=output)
    handlers = root_logger.handlers[:]
    _configure_runtime_logging()
    task_logger.info("configured console")
    assert root_logger.handlers == handlers
    assert output.getvalue().count("configured console") == 1
    assert capsys.readouterr().out == ""


def test_console_reconfiguration_preserves_file_handler(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "workflow.log"
    handler = logging.FileHandler(path)
    root_logger.addHandler(handler)
    try:
        _configure_runtime_logging()
        task_logger.info("automatic")
        assert capsys.readouterr().out.count("automatic") == 1
        output = StringIO()
        configure_console_logging(stream=output)
        _configure_runtime_logging()
        task_logger.info("reconfigured")
        assert capsys.readouterr().out == ""
        assert output.getvalue().count("reconfigured") == 1
        assert path.read_text().splitlines() == ["automatic", "reconfigured"]
    finally:
        root_logger.removeHandler(handler)
        handler.close()


@pytest.mark.parametrize("before_startup", [False, True])
def test_console_opt_out_persists(before_startup: bool, capsys: pytest.CaptureFixture[str]) -> None:
    if not before_startup:
        _configure_runtime_logging()
    configure_console_logging(enabled=False)
    _configure_runtime_logging()
    observability.get_logger("disabled").info("not visible")
    assert capsys.readouterr().out == ""
    assert not observability._console_handlers
    output = StringIO()
    configure_console_logging(stream=output)
    task_logger.info("enabled again")
    assert output.getvalue().count("enabled again") == 1


@pytest.mark.parametrize(("debug", "level"), [("false", "debug"), ("true", "error")])
def test_independent_stream_levels(caplog: pytest.LogCaptureFixture, debug: str, level: str) -> None:
    caplog.set_level(level.upper(), logger=task_logger.name)
    caplog.set_level(logging.DEBUG if debug == "true" else logging.ERROR, logger=internal_logger.name)
    records = _LogQueue()
    root_logger.addHandler(_OTLPQueueHandler(records))
    assert _configure_runtime_logging() is None
    workflow = task_logger
    for severity in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
        logger.log(severity, f"internal-{severity}", task_id="preserved")
        workflow.log(severity, f"workflow-{severity}")
    records.seal()
    exported = list(records.subscribe())
    expected_internal = (
        {"internal-10", "internal-20", "internal-30", "internal-40"} if debug == "true" else {"internal-40"}
    )
    expected_workflow = (
        {"workflow-10", "workflow-20", "workflow-30", "workflow-40"} if level == "debug" else {"workflow-40"}
    )
    assert {record.body.string_value for record in exported} == expected_internal | expected_workflow
    assert len(exported) == len(expected_internal | expected_workflow)
    internal = [record for record in exported if record.body.string_value.startswith("internal-")]
    assert all(
        {item.key: item.value.string_value for item in record.attributes}["task_id"] == "preserved"
        for record in internal
    )


def test_structured_stream_preserves_threaded_records(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger=task_logger.name)
    records = _LogQueue()
    root_logger.addHandler(_OTLPQueueHandler(records))

    local_logger = task_logger
    local_logger.info("filtered")
    threads = [threading.Thread(target=local_logger.warning, args=(f"message-{index}",)) for index in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    def log_failure() -> None:
        raise ValueError("first line\nsecond line")

    try:
        log_failure()
    except ValueError:
        local_logger.exception("failed", extra={"tilebox_structured_log_attributes": {"task": 1}})

    records.seal()
    exported = list(records.subscribe())
    assert {record.body.string_value for record in exported} == {
        *(f"message-{index}" for index in range(20)),
        "failed",
    }
    failure = next(record for record in exported if record.body.string_value == "failed")
    assert failure.severity_text == "ERROR"
    attributes = {item.key: item.value for item in failure.attributes}
    assert "ValueError: first line\nsecond line" in attributes["exception.stacktrace"].string_value
    assert attributes["task"].int_value == 1


@pytest.mark.parametrize("level", ["info", "error"])
def test_bootstrap_before_import(tmp_path: Path, level: str) -> None:
    runtime_id = "66d615f3-7d53-4a31-bc94-94cbb9d9ffa2"
    (tmp_path / "sample_runner.py").write_text(
        "from tilebox.workflows import Runner\n"
        "from tilebox.workflows.observability.logging import get_logger, _get_default_resource\n"
        "print(_get_default_resource().attributes['service.instance.id'])\n"
        "get_logger().info('import-info')\n"
        "get_logger().error('import-error')\n"
        "runner = Runner(tasks=[])\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from unittest.mock import MagicMock, patch
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
exporter = InMemoryLogRecordExporter()
with patch('opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter', return_value=exporter) as factory:
    from tilebox.workflows.runner import __main__ as m
    from tilebox.workflows.observability import logging as logs
    from tilebox.workflows.observability._log_stream import managed_log_queue
    from tilebox.workflows.observability._logging import task_logger, internal_logger
    import os
    assert task_logger.level == (20 if os.environ['TILEBOX_LOG_LEVEL'] == 'info' else 40)
    assert internal_logger.level == 40
    server = MagicMock()
    with patch.object(m, 'WorkerServer', return_value=server):
        m.main(['sample_runner:runner'])
    server.start.assert_called_once_with()
    server.set_runner.assert_called_once()
    assert server.wait.call_count == 2
    server.shutdown.assert_called_once_with()
    logs.initialize_logging('https://ignored.example', 'ignored-key')
    logs._api_handler._logger_provider.force_flush()
    factory.assert_called_once()
    assert [item.log_record.body for item in exporter.get_finished_logs()] == (
        ['import-info', 'import-error'] if task_logger.level == 20 else ['import-error']
    )
    managed_log_queue.seal()
    assert [record.body.string_value for record in managed_log_queue.subscribe()] == (
        ['import-info', 'import-error'] if task_logger.level == 20 else ['import-error']
    )
""",
        ],
        env=os.environ
        | {
            "TILEBOX_RUNTIME_DIR": str(tmp_path),
            "TILEBOX_RUNTIME_TOKEN": "runtime-token",
            "TILEBOX_WORKER_ADDRESS": f"unix://{tmp_path / 'worker.sock'}",
            "TILEBOX_RUNTIME_ID": runtime_id,
            "TILEBOX_API_URL": "https://startup.example",
            "TILEBOX_API_KEY": "startup-key",
            "TILEBOX_LOG_LEVEL": level,
            "TILEBOX_DEBUG": "false",
            "PYTHONPATH": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert result.stdout == runtime_id + "\n"
    assert result.stderr == ""
