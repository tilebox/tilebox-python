import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from protobuf.wkt.google.protobuf.empty_pb import Empty

from _tilebox.uuid import uuid_message_to_optional_uuid
from tilebox.datasets.uuid import must_uuid_to_uuid_message
from tilebox.workflows import ExecutionContext, Runner, Task
from tilebox.workflows.cache import InMemoryCache, JobCache
from tilebox.workflows.data import ExecutionStats, Job, JobState, RunnerContext, TaskState
from tilebox.workflows.data import Task as TaskData
from tilebox.workflows.observability._logging import StructuredLogger
from tilebox.workflows.observability.tracing import NoopWorkflowTracer
from tilebox.workflows.runner.executor import LazyStorageLocations
from tilebox.workflows.runner.worker_server import WorkerServer
from tilebox.workflows.task import TaskMeta
from tilebox.workflows.v1 import core_pb, worker_pb
from tilebox.workflows.v1.worker_connect import WorkerServiceClientSync
from tilebox.workflows.v1.workflows_pb import Workflow as WorkflowMessage


def test_worker_executes_tasks_concurrently_with_isolated_execution_state(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Runtime identity is independent of the runner ID supplied by initialization.
    monkeypatch.setenv("TILEBOX_RUNTIME_ID", str(uuid4()))

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

            cache: JobCache = context.job_cache
            cache[self.label] = self.label.encode()
            context.logger.info("Concurrent task executing", label=self.label)
            context.progress(self.label).add(1)
            self.barrier.wait(timeout=5)
            context.progress(self.label).done(1)

    cache = InMemoryCache()
    runner = Runner(tasks=[ConcurrentTask], cache=cache, context=SharedRunnerContext)
    fake_client = MagicMock()
    fake_client._tracer = NoopWorkflowTracer()
    fake_client._auth = {"url": "https://worker.example", "token": "worker-key"}
    fake_client._task_logger = StructuredLogger(logging.getLogger("tilebox.workflows.tests.shared-worker"))
    caplog.set_level(logging.INFO, logger="tilebox.workflows.tests.shared-worker")

    monkeypatch.setenv("TILEBOX_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("TILEBOX_RUNTIME_TOKEN", "test-token")
    server = WorkerServer(runner, "127.0.0.1:0")
    headers = {"authorization": "Bearer test-token"}

    with (
        patch("tilebox.workflows.runner.worker_service.Client", return_value=fake_client),
        patch("tilebox.workflows.runner.worker_service.initialize_logging") as initialize_logging,
    ):
        server.start()
        stub = WorkerServiceClientSync(f"http://127.0.0.1:{server._port}", timeout_ms=5000)
        stub.initialize_worker(
            worker_pb.InitializeRunnerRequest(runner_id=must_uuid_to_uuid_message(uuid4())),
            headers=headers,
        )
        initialize_logging.assert_called_once_with(url="https://worker.example", token="worker-key")  # noqa: S106

        job = _job()
        tasks = [_task_message(ConcurrentTask(label), job) for label in ("first", "second")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [pool.submit(stub.execute_task, task, headers=headers) for task in tasks]
            try:
                results = [response.result() for response in responses]
            finally:
                stub.shutdown_worker(Empty(), headers=headers)
                stub.close()
                server.wait()

    assert not server._thread.is_alive()
    assert len(SharedRunnerContext.instances) == 1
    computed_tasks = []
    for result in results:
        assert result.computed_task is not None
        computed_tasks.append(result.computed_task)
    assert [task.progress_updates[0].label for task in computed_tasks] == ["first", "second"]
    assert all(task.progress_updates[0].total == 1 for task in computed_tasks)
    assert all(task.progress_updates[0].done == 1 for task in computed_tasks)

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
    task_ids = set()
    for task in tasks:
        assert task.id is not None
        task_ids.add(str(UUID(bytes=task.id.uuid)))
    assert {attributes["task_id"] for attributes in log_attributes} == task_ids


def test_worker_preserves_execution_scope_across_concurrent_descendants(  # noqa: PLR0915
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scopes = [uuid4(), uuid4(), None]
    barrier = threading.Barrier(len(scopes))

    class Grandchild(Task):
        def execute(self, context: ExecutionContext) -> None:
            context.current_task.display = str(context.current_task.identifier.workflow_id)

    class Child(Task):
        def execute(self, context: ExecutionContext) -> None:
            future = context.submit_subtask(Grandchild())
            assert future.identifier().workflow_id == context.current_task.identifier.workflow_id

    class Parent(Task):
        def execute(self, context: ExecutionContext) -> None:
            barrier.wait(timeout=5)
            context.current_task.display = str(context.current_task.identifier.workflow_id)
            futures = [context.submit_subtask(Child()), *context.submit_subtasks([Child(), Child()])]
            assert all(
                future.identifier().workflow_id == context.current_task.identifier.workflow_id for future in futures
            )

    fake_client = MagicMock()
    fake_client._tracer = NoopWorkflowTracer()
    fake_client._auth = {"url": "https://worker.example", "token": "worker-key"}
    fake_client._task_logger = StructuredLogger(logging.getLogger("tilebox.workflows.tests.scoped-worker"))
    monkeypatch.setenv("TILEBOX_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("TILEBOX_RUNTIME_TOKEN", "test-token")
    server = WorkerServer(Runner(tasks=[Parent, Child, Grandchild]), "127.0.0.1:0")
    headers = {"authorization": "Bearer test-token"}

    with (
        patch("tilebox.workflows.runner.worker_service.Client", return_value=fake_client),
        patch("tilebox.workflows.runner.worker_service.initialize_logging"),
    ):
        server.start()
        try:
            with WorkerServiceClientSync(f"http://127.0.0.1:{server._port}", timeout_ms=10000) as worker:
                discovered = worker.list_registered_tasks(Empty(), headers=headers)
                assert len(discovered.identifiers) == 3
                assert all(
                    isinstance(identifier, core_pb.UnboundTaskIdentifier) for identifier in discovered.identifiers
                )
                worker.initialize_worker(
                    worker_pb.InitializeRunnerRequest(
                        runner_id=must_uuid_to_uuid_message(uuid4()),
                        # Release metadata must never override the executing task's scope, especially legacy aliases.
                        workflow=WorkflowMessage(id=must_uuid_to_uuid_message(uuid4()), legacy_task_aliases=True),
                    ),
                    headers=headers,
                )
                job = _job()
                parents = [_task_message(Parent(), job) for _ in scopes]
                for parent, scope in zip(parents, scopes, strict=True):
                    assert parent.identifier is not None
                    parent.identifier.workflow_id = must_uuid_to_uuid_message(scope) if scope is not None else None
                with ThreadPoolExecutor(max_workers=len(scopes)) as pool:
                    futures = [pool.submit(worker.execute_task, parent, headers=headers) for parent in parents]
                    responses = [future.result(timeout=10) for future in futures]
                for response, scope in zip(responses, scopes, strict=True):
                    computed = response.computed_task
                    assert computed is not None
                    assert computed.display == str(scope)
                    children = computed.sub_tasks
                    assert children is not None
                    child_scopes = []
                    for group in children.task_groups:
                        for task_input, pointer in zip(group.inputs, group.identifier_pointers, strict=True):
                            identifier = children.identifier_lookup[pointer]
                            child_scope = uuid_message_to_optional_uuid(identifier.workflow_id)
                            child_scopes.append(child_scope)
                            child = core_pb.Task(
                                id=must_uuid_to_uuid_message(uuid4()),
                                identifier=identifier,
                                input=task_input,
                                job=job.to_message(),
                            )
                            result = worker.execute_task(child, headers=headers).computed_task
                            assert result is not None
                            assert result.sub_tasks is not None
                            grandchildren = result.sub_tasks
                            grandchild_identifier = grandchildren.identifier_lookup[0]
                            assert uuid_message_to_optional_uuid(grandchild_identifier.workflow_id) == child_scope
                            grandchild = core_pb.Task(
                                id=must_uuid_to_uuid_message(uuid4()),
                                identifier=grandchild_identifier,
                                input=grandchildren.task_groups[0].inputs[0],
                                job=job.to_message(),
                            )
                            final = worker.execute_task(grandchild, headers=headers).computed_task
                            assert final is not None
                            assert final.display == str(child_scope)
                    assert child_scopes == [scope, scope, scope]
                assert worker.list_registered_tasks(Empty(), headers=headers) == discovered
                worker.shutdown_worker(Empty(), headers=headers)
        finally:
            server.shutdown()
            server.wait()


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
    client.storage_locations.return_value.all.side_effect = storage_locations
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
    client.storage_locations.return_value.all.assert_called_once_with()
    assert list(locations) == [storage_location.id]


def _job() -> Job:
    return Job(
        id=uuid4(),
        name="concurrent worker test",
        trace_parent="00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        state=JobState.RUNNING,
        submitted_at=datetime.now(tz=UTC),
        progress=[],
        execution_stats=ExecutionStats(None, None, timedelta(), timedelta(), 0, 1, {}),
    )


def _task_message(task: Task, job: Job) -> core_pb.Task:
    identifier = TaskMeta.for_task(task).identifier.bind()
    return TaskData(
        id=uuid4(),
        identifier=identifier,
        state=TaskState.RUNNING,
        input=task._serialize(),
        display=type(task).__name__,
        job=job,
    ).to_message()
