import json
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
from tilebox.workflows.observability import _log_pipe as runtime_logging
from tilebox.workflows.observability import logging as observability
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
    monkeypatch.setattr(observability, "_writer", None)
    monkeypatch.delenv("TILEBOX_LOG_FD", raising=False)
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


def test_absent_fd_adds_one_console_handler(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TILEBOX_LOG_FD", raising=False)
    handler = logging.NullHandler()
    root_logger.addHandler(handler)
    assert _configure_runtime_logging() is None
    assert _configure_runtime_logging() is None
    assert handler in root_logger.handlers
    task_logger.info("console message")
    assert capsys.readouterr().out.endswith(": INFO: console message\n")


def test_existing_console_is_reused(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("TILEBOX_LOG_FD", raising=False)
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
def test_independent_pipe_levels(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, debug: str, level: str
) -> None:
    read_fd, write_fd = os.pipe()
    monkeypatch.setenv("TILEBOX_LOG_FD", str(write_fd))
    caplog.set_level(level.upper(), logger=task_logger.name)
    caplog.set_level(logging.DEBUG if debug == "true" else logging.ERROR, logger=internal_logger.name)
    writer = _configure_runtime_logging()
    assert writer is not None
    assert _configure_runtime_logging() is writer
    workflow = task_logger
    for severity in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
        logger.log(severity, f"internal-{severity}", task_id="preserved")
        workflow.log(severity, f"workflow-{severity}")
    writer.close()
    records = [json.loads(line) for line in os.read(read_fd, 65536).decode().splitlines()]
    os.close(read_fd)
    expected_internal = (
        {"internal-10", "internal-20", "internal-30", "internal-40"} if debug == "true" else {"internal-40"}
    )
    expected_workflow = (
        {"workflow-10", "workflow-20", "workflow-30", "workflow-40"} if level == "debug" else {"workflow-40"}
    )
    assert {r["message"] for r in records} == expected_internal | expected_workflow
    assert len(records) == len(expected_internal | expected_workflow)
    assert all(r["attributes"]["task_id"] == "preserved" for r in records if r["message"].startswith("internal-"))


def test_structured_pipe_is_ndjson_across_threads(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    read_fd, write_fd = os.pipe()
    monkeypatch.setenv("TILEBOX_LOG_FD", str(write_fd))
    caplog.set_level(logging.WARNING, logger=task_logger.name)
    writer = _configure_runtime_logging()
    assert writer is not None
    assert not os.get_inheritable(write_fd)

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

    writer.close()
    data = os.read(read_fd, 1_000_000).decode()
    os.close(read_fd)
    records = [json.loads(line) for line in data.splitlines()]
    assert {record["message"] for record in records} == {*(f"message-{index}" for index in range(20)), "failed"}
    failure = next(record for record in records if record["message"] == "failed")
    assert failure["level"] == "error"
    assert "ValueError: first line\nsecond line" in failure["exception"]
    assert failure["attributes"] == {"task": 1}


def test_idle_writer_shutdown_wakes_blocking_get() -> None:
    read_fd, write_fd = os.pipe()
    waiting = threading.Event()
    original_drain = runtime_logging._PipeWriter._drain

    def observe_get(writer: runtime_logging._PipeWriter) -> None:
        original_get = writer._records.get

        def get() -> bytes | None:
            waiting.set()
            return original_get()

        with patch.object(writer._records, "get", side_effect=get):
            original_drain(writer)

    with patch.object(runtime_logging._PipeWriter, "_drain", observe_get):
        writer = runtime_logging._PipeWriter(write_fd)
        try:
            assert waiting.wait(timeout=2)
            writer.close()
            writer.close()
            assert not writer._thread.is_alive()
        finally:
            writer.close()
            os.close(read_fd)


@pytest.mark.parametrize("count", [3, 256])
def test_shutdown_drains_queued_records_even_when_full(count: int) -> None:
    read_fd, write_fd = os.pipe()
    release = threading.Event()
    original_drain = runtime_logging._PipeWriter._drain

    def delayed_drain(writer: runtime_logging._PipeWriter) -> None:
        release.wait()
        original_drain(writer)

    with (
        patch.object(runtime_logging._PipeWriter, "_drain", delayed_drain),
        patch.object(runtime_logging.os, "write", wraps=os.write) as write,
    ):
        writer = runtime_logging._PipeWriter(write_fd)
        try:
            for index in range(count):
                writer.submit({"i": index})
            # Keep draining paused until close has attempted to enqueue its sentinel.
            writer.close()
            release.set()
            writer.close()
            assert not writer._thread.is_alive()
            records = [json.loads(line) for line in os.read(read_fd, 65536).splitlines()]
            assert records == [{"i": index} for index in range(count)]
            assert write.call_count == 1
        finally:
            release.set()
            writer.close()
            os.close(read_fd)


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
    read_fd, write_fd = os.pipe()
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
from unittest.mock import patch
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
exporter = InMemoryLogRecordExporter()
with patch('opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter', return_value=exporter) as factory:
    from tilebox.workflows.runner import __main__ as m
    from tilebox.workflows.observability import logging as logs
    from tilebox.workflows.observability._logging import task_logger, internal_logger
    import os
    assert task_logger.level == (20 if os.environ['TILEBOX_LOG_LEVEL'] == 'info' else 40)
    assert internal_logger.level == 40
    m.serve_runner = lambda _: None
    m.main(['sample_runner:runner'])
    logs.initialize_logging('https://ignored.example', 'ignored-key')
    logs._api_handler.flush()
    factory.assert_called_once()
    assert [item.log_record.body for item in exporter.get_finished_logs()] == (
        ['import-info', 'import-error'] if task_logger.level == 20 else ['import-error']
    )
""",
            ],
            env=os.environ
            | {
                "TILEBOX_LOG_FD": str(write_fd),
                "TILEBOX_RUNTIME_ID": runtime_id,
                "TILEBOX_API_URL": "https://startup.example",
                "TILEBOX_API_KEY": "startup-key",
                "TILEBOX_LOG_LEVEL": level,
                "TILEBOX_DEBUG": "false",
                "PYTHONPATH": str(tmp_path),
            },
            pass_fds=(write_fd,),
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        records = [json.loads(line) for line in os.read(read_fd, 65536).decode().splitlines()]
    finally:
        os.close(write_fd)
        os.close(read_fd)
    assert result.stdout == runtime_id + "\n"
    assert result.stderr == ""
    assert [record["message"] for record in records] == (
        ["import-info", "import-error"] if level == "info" else ["import-error"]
    )


def test_full_queue_skips_encoding_and_reports_drops() -> None:
    read_fd, write_fd = os.pipe()
    release = threading.Event()
    original_drain = runtime_logging._PipeWriter._drain

    def delayed_drain(writer: runtime_logging._PipeWriter) -> None:
        release.wait()
        original_drain(writer)

    with patch.object(runtime_logging._PipeWriter, "_drain", delayed_drain):
        writer = runtime_logging._PipeWriter(write_fd)
        try:
            for index in range(256):
                writer.submit({"i": index})
            with patch.object(runtime_logging.msgspec.json, "encode") as encode:
                writer.submit({"discarded": 1})
                writer.submit({"discarded": 2})
                encode.assert_not_called()
            assert writer._records.qsize() == 256
            assert writer._records.get_nowait() == b'{"i":0}\n'
            assert writer._records.get_nowait() == b'{"i":1}\n'
            writer.submit({"resumed": True})
            release.set()
            writer.close()
            assert not writer._thread.is_alive()
            records = [json.loads(line) for line in os.read(read_fd, 65536).splitlines()]
            assert records == [
                *({"i": index} for index in range(2, 256)),
                {"level": "warning", "message": "Dropped 2 local log records"},
                {"resumed": True},
            ]
        finally:
            release.set()
            writer.close()
            os.close(read_fd)


@pytest.mark.parametrize("disconnected", [False, True])
def test_failed_pipe_releases_queue_and_skips_future_encoding(*, disconnected: bool) -> None:
    read_fd, write_fd = os.pipe()
    if disconnected:
        os.close(read_fd)
    writer = runtime_logging._PipeWriter(write_fd)
    try:
        # Larger than the pipe buffer: a stalled reader forces a partial write.
        writer.submit({"message": "x" * (512 * 1024)})
        for index in range(8):
            writer.submit({"i": index})
        writer._thread.join(timeout=2)
        assert not writer._thread.is_alive()
        assert writer._records.empty()
        with patch.object(runtime_logging.msgspec.json, "encode") as encode:
            writer.submit({"after_failure": True})
            encode.assert_not_called()
        if not disconnected:
            data = os.read(read_fd, 1024 * 1024)
            assert data.startswith(b'{"message":"xxx')
            assert b"\n" not in data  # No later records appended to a truncated one.
    finally:
        writer.close()
        if not disconnected:
            os.close(read_fd)
