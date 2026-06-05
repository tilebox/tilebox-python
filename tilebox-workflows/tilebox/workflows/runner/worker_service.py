from collections.abc import Callable

import grpc
from google.protobuf.empty_pb2 import Empty

from tilebox.datasets.uuid import uuid_message_to_uuid
from tilebox.workflows.cache import NoCache
from tilebox.workflows.client import Client
from tilebox.workflows.data import Cluster, ComputedTask, FailedTask, Task
from tilebox.workflows.observability.logging import StructuredLogger
from tilebox.workflows.runner.executor import LazyStorageLocations, TaskExecutor
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.task import RunnerContext
from tilebox.workflows.workflows.v1 import core_pb2, worker_pb2, worker_pb2_grpc


class WorkerServiceServicer(worker_pb2_grpc.WorkerServiceServicer):
    def __init__(
        self,
        runner: Runner,
        shutdown: Callable[[], None],
    ) -> None:
        self._runner = runner
        self._shutdown = shutdown
        self._executor: TaskExecutor | None = None

    def ListRegisteredTasks(self, request: Empty, context: grpc.ServicerContext) -> core_pb2.TaskIdentifiers:  # noqa: ARG002, N802
        return core_pb2.TaskIdentifiers(
            identifiers=[identifier.to_message() for identifier in self._runner.task_identifiers]
        )

    def InitializeWorker(  # noqa: N802
        self,
        request: worker_pb2.InitializeRunnerRequest,
        context: grpc.ServicerContext,  # noqa: ARG002
    ) -> worker_pb2.InitializeRunnerResponse:
        runner_id = uuid_message_to_uuid(request.runner_id)
        cluster = Cluster.from_message(request.cluster) if request.HasField("cluster") else None

        api_connection = request.api_connection if request.HasField("api_connection") else None
        api_url = api_connection.url if api_connection and api_connection.url else "https://api.tilebox.com"
        api_token = api_connection.token if api_connection and api_connection.token else None

        client = Client(url=api_url, token=api_token, client_id=runner_id)
        tracer = client._tracer  # noqa: SLF001
        task_logger = StructuredLogger(client._task_logger, {})  # noqa: SLF001

        context_type = self._runner.context or RunnerContext
        runner_context = context_type(tracer)
        runner_context.storage_locations = LazyStorageLocations(client, runner_context)

        self._executor = TaskExecutor(
            self._runner,
            self._runner.cache or NoCache(),
            tracer,
            task_logger,
            runner_context,
            cluster.slug if cluster is not None else "",
        )
        return worker_pb2.InitializeRunnerResponse()

    def ExecuteTask(  # noqa: N802
        self,
        request: core_pb2.Task,
        context: grpc.ServicerContext,  # noqa: ARG002
    ) -> worker_pb2.ExecuteTaskResponse:
        task = Task.from_message(request)
        if self._executor is None:
            failed_task = FailedTask.from_task_error(
                task,
                RuntimeError("Worker is not initialized"),
                was_workflow_error=False,
                progress_updates=[],
            )
            return worker_pb2.ExecuteTaskResponse(failed_task=failed_task.to_message())

        result = self._executor.execute_task(task)
        if isinstance(result, ComputedTask):
            return worker_pb2.ExecuteTaskResponse(computed_task=result.to_message())
        if isinstance(result, FailedTask):
            return worker_pb2.ExecuteTaskResponse(failed_task=result.to_message())
        raise TypeError(f"Unexpected task execution result: {type(result)}")

    def ShutdownWorker(self, request: Empty, context: grpc.ServicerContext) -> Empty:  # noqa: ARG002, N802
        self._shutdown()
        return Empty()
