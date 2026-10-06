import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import grpc
import pytest
from google.protobuf.empty_pb2 import Empty

from tilebox.workflows import Runner
from tilebox.workflows.runner.worker_server import WorkerServer
from tilebox.workflows.runner.worker_service import WorkerServiceServicer
from tilebox.workflows.workflows.v1 import core_pb2, worker_pb2, worker_pb2_grpc

_TOKEN = "test-runtime-token"  # noqa: S105 -- local test credential
_AUTH = (("authorization", f"Bearer {_TOKEN}"),)


@pytest.mark.parametrize("address_from_environment", [False, True])
def test_unmanaged_worker_serves_without_authentication_or_log_stream(
    monkeypatch: pytest.MonkeyPatch, address_from_environment: bool
) -> None:
    monkeypatch.delenv("TILEBOX_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("TILEBOX_RUNTIME_TOKEN", raising=False)
    if address_from_environment:
        monkeypatch.setenv("TILEBOX_WORKER_ADDRESS", "127.0.0.1:0")
    server = WorkerServer(Runner(tasks=[]), None if address_from_environment else "127.0.0.1:0")
    server.start()
    try:
        with grpc.insecure_channel(f"127.0.0.1:{server._port}") as channel:
            worker = worker_pb2_grpc.WorkerServiceStub(channel)
            assert not worker.ListRegisteredTasks(Empty(), timeout=2).identifiers
            with pytest.raises(grpc.RpcError) as error:
                next(worker.WatchLogs(Empty(), timeout=2))
            assert cast(grpc.Call, error.value).code() == grpc.StatusCode.UNAVAILABLE
            worker.ShutdownWorker(Empty(), timeout=2)
    finally:
        server.shutdown()
        server.wait()


def test_shutdown_waits_for_active_task_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    started, release, stopped = threading.Event(), threading.Event(), threading.Event()
    service = WorkerServiceServicer(Runner(tasks=[]), stopped.set)

    def execute(_request: core_pb2.Task) -> worker_pb2.ExecuteTaskResponse:
        started.set()
        assert release.wait(timeout=2)
        assert not stopped.is_set()
        return worker_pb2.ExecuteTaskResponse()

    monkeypatch.setattr(service, "_execute_task", execute)
    task = threading.Thread(target=service.ExecuteTask, args=(core_pb2.Task(), MagicMock()))
    shutdown = threading.Thread(target=service.ShutdownWorker, args=(Empty(), MagicMock()))
    task.start()
    assert started.wait(timeout=1)
    shutdown.start()
    try:
        assert not stopped.wait(timeout=0.05)
    finally:
        release.set()
        task.join(timeout=2)
        shutdown.join(timeout=2)
    assert not task.is_alive()
    assert not shutdown.is_alive()
    assert stopped.is_set()


def _wait_for_file(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while not path.exists():
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            pytest.fail(f"Worker exited before {path.name}: {stdout}\n{stderr}")
        assert time.monotonic() < deadline, f"Timed out waiting for {path}"
        time.sleep(0.01)


def _assert_loading_rpc_contract(worker: worker_pb2_grpc.WorkerServiceStub) -> None:
    for method, request in (
        (worker.ListRegisteredTasks, Empty()),
        (worker.InitializeWorker, worker_pb2.InitializeRunnerRequest()),
        (worker.ExecuteTask, core_pb2.Task()),
        (worker.ShutdownWorker, Empty()),
    ):
        with pytest.raises(grpc.RpcError) as error:
            method(request, timeout=2)
        assert cast(grpc.Call, error.value).code() == grpc.StatusCode.UNAUTHENTICATED
    with pytest.raises(grpc.RpcError) as error:
        next(worker.WatchLogs(Empty(), timeout=2))
    assert cast(grpc.Call, error.value).code() == grpc.StatusCode.UNAUTHENTICATED
    for method, request in (
        (worker.ListRegisteredTasks, Empty()),
        (worker.InitializeWorker, worker_pb2.InitializeRunnerRequest()),
        (worker.ExecuteTask, core_pb2.Task()),
    ):
        with pytest.raises(grpc.RpcError) as error:
            method(request, metadata=_AUTH, timeout=2)
        assert cast(grpc.Call, error.value).code() == grpc.StatusCode.UNAVAILABLE


def _wait_until_loaded(worker: worker_pb2_grpc.WorkerServiceStub) -> None:
    deadline = time.monotonic() + 5
    while True:
        try:
            assert not worker.ListRegisteredTasks(Empty(), metadata=_AUTH, timeout=2).identifiers
        except grpc.RpcError as error:
            if cast(grpc.Call, error).code() != grpc.StatusCode.UNAVAILABLE:
                raise
            assert time.monotonic() < deadline
            time.sleep(0.01)
        else:
            return


@pytest.mark.parametrize(
    "transport", ["tcp", pytest.param("unix", marks=pytest.mark.skipif(os.name == "nt", reason="Unix socket"))]
)
@pytest.mark.parametrize("fail_import", [False, True])
def test_managed_worker_bootstrap_logs_and_shutdown(tmp_path: Path, transport: str, fail_import: bool) -> None:
    # Short Unix paths fit sockaddr_un even when pytest's temporary path is long.
    with tempfile.TemporaryDirectory(prefix="tbw-", dir="/tmp" if transport == "unix" else None) as directory:  # noqa: S108 -- private random directory, short enough for sockaddr_un
        runtime_dir = Path(directory)
        address = f"unix://{runtime_dir / 'worker.sock'}" if transport == "unix" else "127.0.0.1:0"
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
            TILEBOX_WORKER_ADDRESS=address,
            TILEBOX_RUNTIME_DIR=directory,
            TILEBOX_RUNTIME_TOKEN=_TOKEN,
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
                announcement = runtime_dir / "endpoint.json"
                _wait_for_file(announcement, process)
                endpoint = json.loads(announcement.read_text())
                assert endpoint["version"] == 1
                assert _TOKEN not in announcement.read_text()
                assert not (runtime_dir / "endpoint.json.tmp").exists()
                if transport == "unix":
                    assert endpoint["address"] == address
                else:
                    assert endpoint["address"].startswith("127.0.0.1:")
                    assert int(endpoint["address"].split(":")[1]) > 0
                with grpc.insecure_channel(endpoint["address"]) as channel:
                    worker = worker_pb2_grpc.WorkerServiceStub(channel)
                    _assert_loading_rpc_contract(worker)
                    logs = worker.WatchLogs(Empty(), metadata=_AUTH, timeout=10)
                    record = next(logs)
                    assert record.body.string_value == "before workflow loaded"
                    with pytest.raises(grpc.RpcError) as error:
                        next(worker.WatchLogs(Empty(), metadata=_AUTH, timeout=2))
                    assert cast(grpc.Call, error.value).code() == grpc.StatusCode.ALREADY_EXISTS
                    (tmp_path / "load").touch()
                    if not fail_import:
                        _wait_until_loaded(worker)
                        worker.ShutdownWorker(Empty(), metadata=_AUTH, timeout=5)
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
