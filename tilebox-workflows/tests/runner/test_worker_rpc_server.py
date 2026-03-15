import socket
import threading

import grpc

from tilebox.runner.worker.v1 import worker_pb2, worker_pb2_grpc
from tilebox.workflows import ExecutionContext, Task
from tilebox.workflows.runner.worker_rpc_server import serve_worker_rpc
from tilebox.workflows.runner.worker_rpc_v1 import PythonWorkerShim


def _free_address() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()
    return f"{host}:{port}"


class _NoopTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context


def test_worker_rpc_server_transport_lifecycle() -> None:
    address = _free_address()
    shim = PythonWorkerShim(tasks=[_NoopTask])

    server_thread = threading.Thread(target=serve_worker_rpc, args=(shim, address), daemon=True)
    server_thread.start()

    channel = grpc.insecure_channel(address)
    grpc.channel_ready_future(channel).result(timeout=2)
    control_client = worker_pb2_grpc.WorkerControlServiceStub(channel)

    handshake_response = control_client.Handshake(
        worker_pb2.HandshakeRequest(
            supervisor_protocol=worker_pb2.ProtocolVersion(major=1, minor=0),
            worker_runtime="python",
        )
    )
    assert handshake_response.worker_protocol.major == 1

    start_response = control_client.StartWorker(
        worker_pb2.StartWorkerRequest(
            environment_digest="sha256:env",
            runtime_kind="python_uv",
            artifact_uri="file:///artifact.tar.zst",
            artifact_digest="sha256:artifact",
            entrypoint="tilebox_worker:main",
        )
    )
    assert start_response.ready

    health_response = control_client.HealthCheck(
        worker_pb2.HealthCheckRequest(worker_instance_id=start_response.worker_instance_id)
    )
    assert health_response.healthy

    stop_response = control_client.StopWorker(
        worker_pb2.StopWorkerRequest(worker_instance_id=start_response.worker_instance_id)
    )
    assert stop_response.stopped

    shim.request_shutdown("test")
    server_thread.join(timeout=2)
    assert not server_thread.is_alive()
