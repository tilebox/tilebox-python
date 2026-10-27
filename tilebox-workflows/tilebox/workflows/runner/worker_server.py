from __future__ import annotations

import asyncio
import json
import os
import socket
import stat
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from uvicorn._types import ASGIReceiveCallable, ASGIReceiveEvent, ASGISendCallable, Scope

from tilebox.workflows.observability._log_stream import managed_log_queue
from tilebox.workflows.observability.logging import flush_api_logging
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.worker_service import WorkerServiceServicer
from tilebox.workflows.v1.worker_connect import WorkerServiceASGIApplication

WORKER_ADDRESS_ENV = "TILEBOX_WORKER_ADDRESS"
RUNTIME_DIR_ENV = "TILEBOX_RUNTIME_DIR"
RUNTIME_TOKEN_ENV = "TILEBOX_RUNTIME_TOKEN"  # noqa: S105


class _DisconnectAwareApplication:
    """Cancel idle WatchLogs calls when the ASGI transport reports disconnection."""

    def __init__(self, application: WorkerServiceASGIApplication) -> None:
        self._application = application

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        request_task = asyncio.current_task()

        async def receive_with_cancellation() -> ASGIReceiveEvent:
            event = await receive()
            # Connect checks disconnects only after the next yielded record. An
            # idle stream has no next record, so cancel it to run iterator cleanup.
            if event["type"] == "http.disconnect" and request_task is not None:
                request_task.cancel()
            return event

        watch_logs = scope["type"] == "http" and scope["path"] == "/workflows.v1.WorkerService/WatchLogs"
        await self._application(scope, receive_with_cancellation if watch_logs else receive, send)


class WorkerServer:
    """Serve native Connect RPCs over a private Unix socket or authenticated loopback HTTP/1."""

    def __init__(self, runner: Runner | None = None, address: str | None = None) -> None:
        self._address = address or os.environ.get(WORKER_ADDRESS_ENV, "")
        if not self._address:
            raise RuntimeError(f"{WORKER_ADDRESS_ENV} is not set")
        runtime_dir = os.environ.get(RUNTIME_DIR_ENV)
        token = os.environ.get(RUNTIME_TOKEN_ENV)
        if bool(runtime_dir) != bool(token):
            raise RuntimeError(f"{RUNTIME_DIR_ENV} and {RUNTIME_TOKEN_ENV} must be set together")
        self._runtime_dir = Path(runtime_dir) if runtime_dir else None
        if self._address.startswith("unix://"):
            path = Path(self._address.removeprefix("unix://"))
            if not path.is_absolute():
                raise RuntimeError("Worker Unix socket path must be absolute")
            if path.exists():
                if not stat.S_ISSOCK(path.lstat().st_mode):
                    raise RuntimeError("Refusing to remove a non-socket worker endpoint")
                path.unlink()
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.bind(str(path))
            path.chmod(0o600)
            self._port = 0
        else:
            host, _, port = self._address.rpartition(":")
            if host != "127.0.0.1" or not port.isdecimal() or int(port) > 65535:
                raise RuntimeError("Worker TCP addresses must use the 127.0.0.1 loopback interface")
            if not token:
                raise RuntimeError("Worker TCP requires runtime-token authentication")
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.bind((host, int(port)))
            self._port = self._socket.getsockname()[1]
        self._socket.listen(128)
        self._socket.setblocking(False)
        self._service = WorkerServiceServicer(runner, self.shutdown, managed_log_queue, token)
        self._server = uvicorn.Server(
            uvicorn.Config(
                _DisconnectAwareApplication(WorkerServiceASGIApplication(self._service, read_max_bytes=None)),
                http="h11",
                ws="none",
                lifespan="off",
                log_config=None,
                access_log=False,
                timeout_graceful_shutdown=5,
            )
        )
        self._thread = threading.Thread(target=self._server.run, kwargs={"sockets": [self._socket]}, daemon=True)
        self._shutdown_lock = threading.Lock()
        self._shutdown_started = False

    def start(self) -> None:
        self._thread.start()
        deadline = time.monotonic() + 5
        while not self._server.started:
            if not self._thread.is_alive() or time.monotonic() >= deadline:
                self.shutdown()
                raise RuntimeError("Worker HTTP server failed to start")
            time.sleep(0.005)
        if self._runtime_dir is not None:
            try:
                self._announce()
            except BaseException:
                self.shutdown()
                self.wait()
                raise

    def set_runner(self, runner: Runner) -> None:
        self._service.set_runner(runner)

    def wait(self) -> None:
        self._thread.join()

    def shutdown(self) -> None:
        with self._shutdown_lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True
        threading.Thread(target=self._shutdown, name="tilebox-worker-shutdown", daemon=True).start()

    def _shutdown(self) -> None:
        # Exporters are third-party code: do not let a stalled flush pin shutdown.
        flush = threading.Thread(target=flush_api_logging, daemon=True)
        flush.start()
        flush.join(timeout=2)
        if managed_log_queue is not None:
            managed_log_queue.seal()
            managed_log_queue.wait_empty(timeout=1)
        self._server.should_exit = True

    def _announce(self) -> None:
        assert self._runtime_dir is not None
        address = self._address if self._address.startswith("unix://") else f"127.0.0.1:{self._port}"
        temporary = self._runtime_dir / "endpoint.json.tmp"
        temporary.write_text(
            json.dumps({"version": 2, "protocol": "connect", "address": address}, separators=(",", ":"))
        )
        temporary.replace(self._runtime_dir / "endpoint.json")


def serve_runner(runner: Runner, address: str | None = None) -> None:
    server = WorkerServer(runner, address)
    server.start()
    try:
        server.wait()
    finally:
        server.shutdown()
        server.wait()
