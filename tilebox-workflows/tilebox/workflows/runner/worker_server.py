import os
import threading
from concurrent import futures
from pathlib import Path

import grpc

from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.worker_service import WorkerServiceServicer
from tilebox.workflows.workflows.v1 import worker_pb2_grpc

WORKER_ADDRESS_ENV = "TILEBOX_WORKER_ADDRESS"


def serve_runner(runner: Runner, address: str | None = None) -> None:
    address = address or os.environ.get(WORKER_ADDRESS_ENV)
    if not address:
        raise RuntimeError(
            f"{WORKER_ADDRESS_ENV} is not set. Set it to a local gRPC address, for example "
            f"'unix:///tmp/tilebox-worker.sock'."
        )

    bind_address = _normalize_grpc_address(address)
    _unlink_stale_unix_socket(bind_address)

    server = grpc.server(futures.ThreadPoolExecutor())

    def shutdown() -> None:
        # server.stop() is blocking, so we run it in a separate thread
        # server.stop(5) means we stop accepting new requests immediately, but we give existing requests up to 5
        # seconds to finish before we forcefully terminate them
        threading.Thread(target=server.stop, args=(5,), daemon=True).start()

    worker_pb2_grpc.add_WorkerServiceServicer_to_server(WorkerServiceServicer(runner, shutdown), server)
    port = server.add_insecure_port(bind_address)
    if port == 0:
        raise RuntimeError(f"Failed to bind worker server to {address!r}")

    server.start()
    server.wait_for_termination()


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
        socket_path.unlink()
