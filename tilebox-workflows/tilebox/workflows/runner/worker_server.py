import json
import os
import threading
from concurrent import futures
from pathlib import Path

import grpc

from tilebox.workflows.observability._log_stream import managed_log_queue
from tilebox.workflows.observability._logging import logger
from tilebox.workflows.observability.logging import flush_api_logging
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.worker_service import WorkerServiceServicer
from tilebox.workflows.workflows.v1 import worker_pb2_grpc

WORKER_ADDRESS_ENV = "TILEBOX_WORKER_ADDRESS"
RUNTIME_DIR_ENV = "TILEBOX_RUNTIME_DIR"
RUNTIME_TOKEN_ENV = "TILEBOX_RUNTIME_TOKEN"  # noqa: S105 -- environment variable name, not a credential


class WorkerServer:
    """Python worker server for a runner started from the Tilebox CLI.

    This server is the interface the CLI uses to communicate with the Python process.
    """

    def __init__(self, runner: Runner | None = None, address: str | None = None) -> None:
        # Older CLIs and direct serve_runner() callers use the configured address
        # without runtime-token authentication, endpoint discovery, or live log streaming.
        self._managed = bool(os.environ.get(RUNTIME_DIR_ENV) and os.environ.get(RUNTIME_TOKEN_ENV))
        configured_address = address or os.environ.get(WORKER_ADDRESS_ENV)
        if not configured_address:
            raise RuntimeError(
                f"{WORKER_ADDRESS_ENV} is not set. Set it to a local gRPC address, for example "
                f"'unix:///tmp/tilebox-worker.sock'."
            )
        self._address = configured_address
        runtime_dir = os.environ.get(RUNTIME_DIR_ENV)
        runtime_token = os.environ.get(RUNTIME_TOKEN_ENV)
        if bool(runtime_dir) != bool(runtime_token):
            raise RuntimeError(f"{RUNTIME_DIR_ENV} and {RUNTIME_TOKEN_ENV} must be set together")
        self._bind_address = _normalize_grpc_address(configured_address)
        if self._managed and not configured_address.startswith("unix://"):
            host, _, port = configured_address.rpartition(":")
            if host != "127.0.0.1" or not port.isdecimal() or int(port) > 65535:
                raise RuntimeError("Managed worker TCP addresses must use the 127.0.0.1 loopback interface")
        _unlink_stale_unix_socket(self._bind_address)
        self._server = grpc.server(futures.ThreadPoolExecutor())
        self._service = WorkerServiceServicer(
            runner,
            self.shutdown,
            managed_log_queue if self._managed else None,
            os.environ.get(RUNTIME_TOKEN_ENV) if self._managed else None,
        )
        worker_pb2_grpc.add_WorkerServiceServicer_to_server(self._service, self._server)
        self._port = self._server.add_insecure_port(self._bind_address)
        if self._port == 0:
            raise RuntimeError(f"Failed to bind worker server to {configured_address!r}")
        self._shutdown_lock = threading.Lock()
        self._shutdown_started = False

    def start(self) -> None:
        self._server.start()
        try:
            if self._managed:
                self._announce()
        except BaseException:
            self._server.stop(0).wait()
            raise

    def set_runner(self, runner: Runner) -> None:
        self._service.set_runner(runner)

    def wait(self) -> None:
        self._server.wait_for_termination()

    def shutdown(self) -> None:
        with self._shutdown_lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True
        threading.Thread(target=self._shutdown, name="tilebox-worker-shutdown", daemon=True).start()

    def _shutdown(self) -> None:
        try:
            flush_api_logging()
        finally:
            if self._managed and managed_log_queue is not None:
                managed_log_queue.seal()
                managed_log_queue.wait_empty(timeout=1.0)
            self._server.stop(5).wait()

    def _announce(self) -> None:
        runtime_dir = Path(os.environ[RUNTIME_DIR_ENV])
        address = self._address
        if not address.startswith("unix://"):
            address = f"127.0.0.1:{self._port}"
        temporary = runtime_dir / "endpoint.json.tmp"
        temporary.write_text(json.dumps({"version": 1, "address": address}, separators=(",", ":")))
        temporary.replace(runtime_dir / "endpoint.json")


def serve_runner(runner: Runner, address: str | None = None) -> None:
    server = WorkerServer(runner, address)
    server.start()
    try:
        server.wait()
    finally:
        server.shutdown()
        server.wait()


def _normalize_grpc_address(address: str) -> str:
    if address.startswith("unix://"):
        return "unix:" + address.removeprefix("unix://")
    return address


def _unlink_stale_unix_socket(address: str) -> None:
    if not address.startswith("unix:"):
        return
    path = address.removeprefix("unix:")
    if not path:
        return
    socket_path = Path(path)
    if socket_path.exists():
        logger.debug(f"Removing stale worker Unix socket {socket_path}")
        socket_path.unlink()
