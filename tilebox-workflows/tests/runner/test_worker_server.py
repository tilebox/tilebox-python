import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from protobuf.wkt.google.protobuf.empty_pb import Empty
from tests.log_values import string_value

from tilebox.workflows import Runner
from tilebox.workflows._otel.opentelemetry.proto.logs.v1.logs_pb import LogRecord
from tilebox.workflows.observability._log_stream import _any_value, _LogQueue
from tilebox.workflows.runner import worker_server
from tilebox.workflows.runner.worker_server import WorkerServer
from tilebox.workflows.v1 import core_pb, worker_pb
from tilebox.workflows.v1.worker_connect import WorkerServiceClientSync

_TOKEN = "test-runtime-token"  # noqa: S105 -- local test credential
_AUTH = {"authorization": f"Bearer {_TOKEN}"}


def _wait_for_file(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while not path.exists():
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            pytest.fail(f"Worker exited before {path.name}: {stdout}\n{stderr}")
        assert time.monotonic() < deadline, f"Timed out waiting for {path}"
        time.sleep(0.01)


@pytest.mark.parametrize("fail_import", [False, True])
def test_managed_worker_bootstrap_logs_and_shutdown(tmp_path: Path, fail_import: bool) -> None:  # noqa: PLR0915 -- full process lifecycle
    """Exercise authenticated real HTTP/1 RPCs while workflow imports block the main thread."""
    source = """
import time
from pathlib import Path
from tilebox.workflows import Runner
from tilebox.workflows.observability.logging import get_logger
get_logger().warning("before workflow loaded")
print("raw stdout", flush=True)
while not Path("load").exists():
    time.sleep(0.01)
"""
    source += 'raise RuntimeError("broken workflow")\n' if fail_import else "runner = Runner(tasks=[])\n"
    (tmp_path / "fixture.py").write_text(source)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("TILEBOX_")}
    environment.update(
        TILEBOX_WORKER_ADDRESS="127.0.0.1:0", TILEBOX_RUNTIME_DIR=str(tmp_path), TILEBOX_RUNTIME_TOKEN=_TOKEN
    )
    with subprocess.Popen(
        [sys.executable, "-m", "tilebox.workflows.runner", "fixture:runner"],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        try:
            announcement = tmp_path / "endpoint.json"
            _wait_for_file(announcement, process)
            endpoint = json.loads(announcement.read_text())
            assert endpoint["version"] == 2
            assert endpoint["protocol"] == "connect"
            assert _TOKEN not in announcement.read_text()
            assert not (tmp_path / "endpoint.json.tmp").exists()
            with WorkerServiceClientSync(f"http://{endpoint['address']}", timeout_ms=3000) as worker:
                for call in (
                    lambda: worker.list_registered_tasks(Empty()),
                    lambda: worker.initialize_worker(worker_pb.InitializeRunnerRequest()),
                    lambda: worker.execute_task(core_pb.Task()),
                    lambda: worker.shutdown_worker(Empty()),
                ):
                    with pytest.raises(ConnectError) as error:
                        call()
                    assert error.value.code == Code.UNAUTHENTICATED
                with pytest.raises(ConnectError) as error:
                    next(worker.watch_logs(Empty()))
                assert error.value.code == Code.UNAUTHENTICATED
                for call in (
                    lambda: worker.list_registered_tasks(Empty(), headers=_AUTH),
                    lambda: worker.initialize_worker(worker_pb.InitializeRunnerRequest(), headers=_AUTH),
                    lambda: worker.execute_task(core_pb.Task(), headers=_AUTH),
                ):
                    with pytest.raises(ConnectError) as error:
                        call()
                    assert error.value.code == Code.UNAVAILABLE
                logs = worker.watch_logs(Empty(), headers=_AUTH, timeout_ms=10000)
                assert string_value(next(logs).body) == "before workflow loaded"
                with pytest.raises(ConnectError) as error:
                    next(worker.watch_logs(Empty(), headers=_AUTH))
                assert error.value.code == Code.ALREADY_EXISTS
                (tmp_path / "load").touch()
                if not fail_import:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            assert not worker.list_registered_tasks(Empty(), headers=_AUTH).identifiers
                            break
                        except ConnectError as error:
                            if error.code != Code.UNAVAILABLE:
                                raise
                            assert time.monotonic() < deadline
                            time.sleep(0.01)
                    worker.shutdown_worker(Empty(), headers=_AUTH)
                assert list(logs) == []
            stdout, stderr = process.communicate(timeout=10)
            assert stdout == "raw stdout\n"
            if fail_import:
                assert process.returncode != 0
                assert "broken workflow" in stderr
            else:
                assert process.returncode == 0, stderr
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


@pytest.mark.skipif(os.name == "nt", reason="Unix socket")
def test_unix_worker_authenticates_real_connect_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Unix permissions, endpoint discovery, and auth without a gRPC transport."""
    with tempfile.TemporaryDirectory(prefix="tbw-", dir="/tmp") as directory:
        path = Path(directory)
        monkeypatch.setenv("TILEBOX_RUNTIME_DIR", directory)
        monkeypatch.setenv("TILEBOX_RUNTIME_TOKEN", _TOKEN)
        server = WorkerServer(Runner(tasks=[]), f"unix://{path / 'worker.sock'}")
        server.start()
        try:
            assert (path / "worker.sock").stat().st_mode & 0o777 == 0o600
            assert json.loads((path / "endpoint.json").read_text())["protocol"] == "connect"
            for authorized in (False, True):
                connection = http.client.HTTPConnection("localhost", timeout=3)
                connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                connection.sock.settimeout(3)
                connection.sock.connect(str(path / "worker.sock"))
                try:
                    headers = {"Content-Type": "application/proto", **(_AUTH if authorized else {})}
                    connection.request("POST", "/workflows.v1.WorkerService/ListRegisteredTasks", b"", headers)
                    response = connection.getresponse()
                    assert response.status == (200 if authorized else 401)
                    if authorized:
                        assert not core_pb.UnboundTaskIdentifiers.from_binary(response.read()).identifiers
                finally:
                    connection.close()
        finally:
            server.shutdown()
            server.wait()


def test_tcp_worker_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject unsecured TCP listeners and non-loopback addresses before binding."""
    monkeypatch.delenv("TILEBOX_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("TILEBOX_RUNTIME_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="authentication"):
        WorkerServer(address="127.0.0.1:0")
    with pytest.raises(RuntimeError, match="loopback"):
        WorkerServer(address="0.0.0.0:0")


def test_log_cancellation_allows_reconnection_without_stopping_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cancel an HTTP/1 log stream, reconnect, and retain unary readiness."""
    monkeypatch.setenv("TILEBOX_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("TILEBOX_RUNTIME_TOKEN", _TOKEN)
    records = _LogQueue()
    monkeypatch.setattr(worker_server, "managed_log_queue", records)
    records.submit(LogRecord(body=_any_value("first")))
    server = WorkerServer(Runner(tasks=[]), "127.0.0.1:0")
    server.start()
    try:
        # Disposing the transport cancels the response without assuming that the
        # public Iterator return type exposes generator-specific close methods.
        with WorkerServiceClientSync(f"http://127.0.0.1:{server._port}", timeout_ms=2000) as initial_client:
            stream = initial_client.watch_logs(Empty(), headers=_AUTH)
            assert string_value(next(stream).body) == "first"
        with WorkerServiceClientSync(f"http://127.0.0.1:{server._port}", timeout_ms=2000) as client:
            deadline = time.monotonic() + 2
            # Do not enqueue a record to wake the old stream: disconnection must
            # release even an idle subscriber, and delivery across cancel races
            # is best-effort rather than an acknowledgement protocol.
            while True:
                stream = client.watch_logs(Empty(), headers=_AUTH, timeout_ms=100)
                try:
                    next(stream)
                    pytest.fail("Idle WatchLogs unexpectedly returned a record")
                except ConnectError as error:
                    if error.code == Code.DEADLINE_EXCEEDED:
                        break  # Accepted a new subscription without any queued records.
                    if error.code != Code.ALREADY_EXISTS:
                        raise
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
            assert not client.list_registered_tasks(Empty(), headers=_AUTH).identifiers
            client.shutdown_worker(Empty(), headers=_AUTH)
    finally:
        server.shutdown()
        server.wait()


def test_task_deadline_does_not_skip_cleanup_on_shutdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A canceled execution keeps cleanup active while unrelated unary RPCs remain responsive."""
    monkeypatch.setenv("TILEBOX_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("TILEBOX_RUNTIME_TOKEN", _TOKEN)
    started, release, cleaned = threading.Event(), threading.Event(), threading.Event()
    server = WorkerServer(Runner(tasks=[]), "127.0.0.1:0")

    def execute(_request: core_pb.Task) -> worker_pb.ExecuteTaskResponse:
        started.set()
        try:
            assert release.wait(timeout=3)
            return worker_pb.ExecuteTaskResponse()
        finally:
            cleaned.set()

    monkeypatch.setattr(server._service, "_execute_task", execute)
    server.start()
    try:
        with (
            WorkerServiceClientSync(f"http://127.0.0.1:{server._port}", timeout_ms=2000) as client,
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            task = pool.submit(client.execute_task, core_pb.Task(), headers=_AUTH, timeout_ms=100)
            assert started.wait(timeout=1)
            with pytest.raises(ConnectError) as error:
                task.result(timeout=2)
            assert error.value.code == Code.DEADLINE_EXCEEDED
            assert not client.list_registered_tasks(Empty(), headers=_AUTH).identifiers
            shutdown = pool.submit(client.shutdown_worker, Empty(), headers=_AUTH)
            try:
                time.sleep(0.05)
                assert not shutdown.done()
            finally:
                release.set()
            shutdown.result(timeout=2)
            assert cleaned.is_set()
    finally:
        release.set()
        server.shutdown()
        server.wait()
