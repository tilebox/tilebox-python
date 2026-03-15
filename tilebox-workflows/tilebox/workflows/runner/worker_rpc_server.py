from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import grpc

from tilebox.runner.worker.v1 import worker_pb2, worker_pb2_grpc
from tilebox.workflows.runner.worker_rpc_v1 import (
    ProtocolVersionMismatchError,
    PythonWorkerShim,
    RequiredCapabilitiesMissingError,
)


def _rpc_bind_address(value: str) -> str:
    if "://" not in value:
        return value

    parsed = urlparse(value)
    if parsed.scheme == "unix":
        if parsed.path == "":
            msg = f"Invalid worker RPC unix address {value!r}; expected unix:///absolute/path"
            raise ValueError(msg)
        return value

    if parsed.hostname is None or parsed.port is None:
        msg = f"Invalid worker RPC address {value!r}; expected host:port or URL with host and port"
        raise ValueError(msg)

    return f"{parsed.hostname}:{parsed.port}"


class _WorkerControlServicer(worker_pb2_grpc.WorkerControlServiceServicer):
    def __init__(self, shim: PythonWorkerShim) -> None:
        self._shim = shim

    def Handshake(  # noqa: N802
        self,
        request: worker_pb2.HandshakeRequest,
        context: grpc.ServicerContext,
    ) -> worker_pb2.HandshakeResponse:
        _ = context
        try:
            return self._shim.handshake(request)
        except (ProtocolVersionMismatchError, RequiredCapabilitiesMissingError) as error:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(error))

    def StartWorker(  # noqa: N802
        self,
        request: worker_pb2.StartWorkerRequest,
        context: grpc.ServicerContext,
    ) -> worker_pb2.StartWorkerResponse:
        _ = context
        return self._shim.start_worker(request)

    def StopWorker(  # noqa: N802
        self,
        request: worker_pb2.StopWorkerRequest,
        context: grpc.ServicerContext,
    ) -> worker_pb2.StopWorkerResponse:
        _ = context
        return self._shim.stop_worker(request)

    def HealthCheck(  # noqa: N802
        self,
        request: worker_pb2.HealthCheckRequest,
        context: grpc.ServicerContext,
    ) -> worker_pb2.HealthCheckResponse:
        _ = context
        return self._shim.health_check(request)


class _WorkerExecutionServicer(worker_pb2_grpc.WorkerExecutionServiceServicer):
    def __init__(self, shim: PythonWorkerShim) -> None:
        self._shim = shim

    def ExecuteTask(  # noqa: N802
        self,
        request: worker_pb2.ExecuteTaskRequest,
        context: grpc.ServicerContext,
    ) -> worker_pb2.ExecuteTaskResponse:
        _ = context
        return self._shim.execute_task(request)

    def CancelTask(  # noqa: N802
        self,
        request: worker_pb2.CancelTaskRequest,
        context: grpc.ServicerContext,
    ) -> worker_pb2.CancelTaskResponse:
        _ = context
        return self._shim.cancel_task(request)


def serve_worker_rpc(shim: PythonWorkerShim, address: str) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=8))
    worker_pb2_grpc.add_WorkerControlServiceServicer_to_server(_WorkerControlServicer(shim), server)
    worker_pb2_grpc.add_WorkerExecutionServiceServicer_to_server(_WorkerExecutionServicer(shim), server)

    bound_port = server.add_insecure_port(_rpc_bind_address(address))
    if bound_port <= 0:
        msg = f"Failed to bind worker RPC server to {address!r}"
        raise RuntimeError(msg)

    with shim.graceful_shutdown():
        server.start()
        try:
            while not shim.is_shutting_down():
                time.sleep(0.1)
        finally:
            server.stop(grace=5).wait()


def main() -> int:
    rpc_address = os.getenv("TILEBOX_WORKER_RPC_ADDRESS")
    if not rpc_address:
        msg = "TILEBOX_WORKER_RPC_ADDRESS must be set"
        raise RuntimeError(msg)

    shim = PythonWorkerShim(
        expected_environment_digest=os.getenv("TILEBOX_WORKER_ENVIRONMENT_DIGEST") or None,
        expected_artifact_digest=os.getenv("TILEBOX_WORKER_ARTIFACT_DIGEST") or None,
        expected_entrypoint=os.getenv("TILEBOX_WORKER_ENTRYPOINT") or None,
    )
    serve_worker_rpc(shim=shim, address=rpc_address)
    return 0
