import asyncio
import logging
import socket
import threading
from datetime import datetime, timedelta, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import grpc
import pytest
from google.protobuf.empty_pb2 import Empty

from tilebox.datasets.uuid import must_uuid_to_uuid_message
from tilebox.workflows import ExecutionContext, Runner, Task
from tilebox.workflows.cache import InMemoryCache, JobCache
from tilebox.workflows.data import ExecutionStats, Job, JobState, RunnerContext, TaskState
from tilebox.workflows.data import Task as TaskData
from tilebox.workflows.observability.tracing import NoopWorkflowTracer
from tilebox.workflows.runner.executor import LazyStorageLocations
from tilebox.workflows.runner.worker_server import serve_runner
from tilebox.workflows.task import TaskMeta
from tilebox.workflows.workflows.v1 import core_pb2, worker_pb2, worker_pb2_grpc


def test_worker_executes_tasks_concurrently_with_isolated_execution_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class SharedRunnerContext(RunnerContext):
        instances: ClassVar[list["SharedRunnerContext"]] = []

        def __init__(self, tracer: NoopWorkflowTracer) -> None:
            super().__init__(tracer)
            self.instances.append(self)

    class ConcurrentTask(Task):
        label: str

        barrier: ClassVar[threading.Barrier] = threading.Barrier(2)
        observations: ClassVar[list[tuple[str, int, int, int, int]]] = []
        observations_lock = threading.Lock()

        async def execute(self, context: ExecutionContext) -> None:
            await asyncio.sleep(0)
            with self.observations_lock:
                self.observations.append(
                    (self.label, id(self), id(context), id(context.runner_context), id(asyncio.get_running_loop()))
                )

            cache: JobCache = context.job_cache  # ty: ignore[unresolved-attribute]
            cache[self.label] = self.label.encode()
            context.logger.info("Concurrent task executing", label=self.label)
            context.progress(self.label).add(1)
            self.barrier.wait(timeout=5)
            context.progress(self.label).done(1)

    cache = InMemoryCache()
    runner = Runner(tasks=[ConcurrentTask], cache=cache, context=SharedRunnerContext)
    fake_client = MagicMock()
    fake_client._tracer = NoopWorkflowTracer()
    fake_client._task_logger = logging.getLogger("tilebox.workflows.tests.shared-worker")
    caplog.set_level(logging.INFO, logger=fake_client._task_logger.name)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as free_socket:
        free_socket.bind(("127.0.0.1", 0))
        address = f"127.0.0.1:{free_socket.getsockname()[1]}"

    server_thread = threading.Thread(target=serve_runner, args=(runner, address), daemon=True)

    with patch("tilebox.workflows.runner.worker_service.Client", return_value=fake_client):
        server_thread.start()
        channel = grpc.insecure_channel(address)
        grpc.channel_ready_future(channel).result(timeout=5)
        stub = worker_pb2_grpc.WorkerServiceStub(channel)
        stub.InitializeWorker(
            worker_pb2.InitializeRunnerRequest(runner_id=must_uuid_to_uuid_message(uuid4())),
            timeout=5,
        )

        job = _job()
        tasks = [_task_message(ConcurrentTask(label), job) for label in ("first", "second")]
        responses = [stub.ExecuteTask.future(task, timeout=5) for task in tasks]

        try:
            results = [response.result() for response in responses]
        finally:
            stub.ShutdownWorker(Empty(), timeout=5)
            channel.close()
            server_thread.join(timeout=10)

    assert not server_thread.is_alive()
    assert len(SharedRunnerContext.instances) == 1
    assert all(result.HasField("computed_task") for result in results)
    assert [result.computed_task.progress_updates[0].label for result in results] == ["first", "second"]
    assert all(result.computed_task.progress_updates[0].total == 1 for result in results)
    assert all(result.computed_task.progress_updates[0].done == 1 for result in results)

    assert {observation[0] for observation in ConcurrentTask.observations} == {"first", "second"}
    assert len({observation[1] for observation in ConcurrentTask.observations}) == 2
    assert len({observation[2] for observation in ConcurrentTask.observations}) == 2
    assert {observation[3] for observation in ConcurrentTask.observations} == {id(SharedRunnerContext.instances[0])}
    assert len({observation[4] for observation in ConcurrentTask.observations}) == 2
    assert sorted(cache.group(str(job.id)).items()) == [("first", b"first"), ("second", b"second")]

    log_attributes = [
        record.tilebox_structured_log_attributes  # ty: ignore[unresolved-attribute]
        for record in caplog.records
        if record.message == "Concurrent task executing"
    ]
    assert {attributes["label"] for attributes in log_attributes} == {"first", "second"}
    assert {attributes["task_id"] for attributes in log_attributes} == {str(UUID(bytes=task.id.uuid)) for task in tasks}


def test_lazy_storage_locations_are_loaded_once_during_concurrent_access() -> None:
    storage_location = MagicMock()
    storage_location.id = UUID(int=1)
    storage_location._with_runner_context.return_value = storage_location

    load_started = threading.Event()
    release_load = threading.Event()

    def storage_locations() -> list[MagicMock]:
        load_started.set()
        release_load.wait(timeout=5)
        return [storage_location]

    client = MagicMock()
    client.automations.return_value.storage_locations.side_effect = storage_locations
    locations = LazyStorageLocations(client, RunnerContext())

    first = threading.Thread(target=len, args=(locations,))
    first.start()
    assert load_started.wait(timeout=5)

    second_access_started = threading.Event()

    def read_locations() -> None:
        second_access_started.set()
        len(locations)

    second = threading.Thread(target=read_locations)
    second.start()
    assert second_access_started.wait(timeout=5)
    release_load.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    client.automations.return_value.storage_locations.assert_called_once_with()
    assert list(locations) == [storage_location.id]


def _job() -> Job:
    return Job(
        id=uuid4(),
        name="concurrent worker test",
        trace_parent="00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        state=JobState.RUNNING,
        submitted_at=datetime.now(tz=timezone.utc),
        progress=[],
        execution_stats=ExecutionStats(None, None, timedelta(), timedelta(), 0, 1, {}),
    )


def _task_message(task: Task, job: Job) -> core_pb2.Task:
    identifier = TaskMeta.for_task(task).identifier
    return TaskData(
        id=uuid4(),
        identifier=identifier,
        state=TaskState.RUNNING,
        input=task._serialize(),
        display=type(task).__name__,
        job=job,
    ).to_message()
