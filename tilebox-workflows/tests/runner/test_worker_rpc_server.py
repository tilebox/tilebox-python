import socket
import threading
from typing import ClassVar
from uuid import uuid4

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


class _BlockingTask(Task):
    started: ClassVar[threading.Event] = threading.Event()
    release: ClassVar[threading.Event] = threading.Event()

    def execute(self, context: ExecutionContext) -> None:
        _ = context
        _BlockingTask.started.set()
        _BlockingTask.release.wait(timeout=2)


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


def test_control_requests_remain_responsive_while_task_runs() -> None:
    address = _free_address()
    shim = PythonWorkerShim(tasks=[_BlockingTask])

    _BlockingTask.started.clear()
    _BlockingTask.release.clear()

    server_thread = threading.Thread(target=serve_worker_rpc, args=(shim, address), daemon=True)
    server_thread.start()

    channel = grpc.insecure_channel(address)
    grpc.channel_ready_future(channel).result(timeout=2)
    control_client = worker_pb2_grpc.WorkerControlServiceStub(channel)
    execution_client = worker_pb2_grpc.WorkerExecutionServiceStub(channel)

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

    execute_request = worker_pb2.ExecuteTaskRequest(
        worker_instance_id=start_response.worker_instance_id,
        task_id=str(uuid4()),
        job_id=str(uuid4()),
        task_identifier_name="_BlockingTask",
        task_identifier_version="v0.0",
        task_input=_BlockingTask()._serialize(),
        task_display="blocking-task",
    )

    execution_done = threading.Event()

    def _run_task() -> None:
        execution_client.ExecuteTask(execute_request, timeout=5)
        execution_done.set()

    execution_thread = threading.Thread(target=_run_task)
    execution_thread.start()
    assert _BlockingTask.started.wait(timeout=1)

    try:
        health_response = control_client.HealthCheck(
            worker_pb2.HealthCheckRequest(worker_instance_id=start_response.worker_instance_id),
            timeout=0.5,
        )
        assert health_response.healthy
    finally:
        _BlockingTask.release.set()

    execution_thread.join(timeout=2)
    assert execution_done.is_set()

    shim.request_shutdown("test")
    server_thread.join(timeout=2)
    assert not server_thread.is_alive()
