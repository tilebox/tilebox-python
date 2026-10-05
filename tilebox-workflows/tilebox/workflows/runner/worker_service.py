import hmac
import threading
from collections.abc import Callable, Iterator

import grpc
from google.protobuf.empty_pb2 import Empty
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord

from tilebox.datasets.uuid import uuid_message_to_uuid
from tilebox.workflows.cache import NoCache
from tilebox.workflows.client import Client
from tilebox.workflows.data import Cluster, ComputedTask, FailedTask, Task
from tilebox.workflows.observability._log_stream import _LogQueue
from tilebox.workflows.observability._logging import logger
from tilebox.workflows.observability.logging import initialize_logging
from tilebox.workflows.runner.executor import LazyStorageLocations, TaskExecutor
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.task import RunnerContext
from tilebox.workflows.workflows.v1 import core_pb2, worker_pb2, worker_pb2_grpc


class WorkerServiceServicer(worker_pb2_grpc.WorkerServiceServicer):
    def __init__(
        self,
        runner: Runner | None,
        shutdown: Callable[[], None],
        logs: _LogQueue | None = None,
        token: str | None = None,
    ) -> None:
        self._runner = runner
        self._shutdown = shutdown
        self._executor: TaskExecutor | None = None
        self._logs = logs
        self._token = token
        self._tasks = threading.Condition()
        self._active_tasks = 0
        self._stopping = False

    def _authorize(self, context: grpc.ServicerContext) -> None:
        if self._token is None:
            return
        metadata = dict(context.invocation_metadata())
        supplied = metadata.get("authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {self._token}"):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid runtime authorization")

    def set_runner(self, runner: Runner) -> None:
        self._runner = runner

    def _loaded_runner(self, context: grpc.ServicerContext) -> Runner:
        runner = self._runner
        if runner is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Worker runtime is still loading")
            raise RuntimeError("Worker runtime is still loading")
        return runner

    def ListRegisteredTasks(self, request: Empty, context: grpc.ServicerContext) -> core_pb2.TaskIdentifiers:  # noqa: ARG002, N802
        logger.debug("ListRegisteredTasks RPC called")
        self._authorize(context)
        runner = self._loaded_runner(context)
        identifiers = [identifier.to_message() for identifier in runner.task_identifiers]
        logger.debug(f"ListRegisteredTasks RPC returning {len(identifiers)} task identifier(s)")
        return core_pb2.TaskIdentifiers(identifiers=identifiers)

    def InitializeWorker(  # noqa: N802
        self,
        request: worker_pb2.InitializeRunnerRequest,
        context: grpc.ServicerContext,
    ) -> worker_pb2.InitializeRunnerResponse:
        logger.debug("InitializeWorker RPC called")
        self._authorize(context)
        runner = self._loaded_runner(context)
        runner_id = uuid_message_to_uuid(request.runner_id)
        if self._executor is not None:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Worker is already initialized")
        cluster = Cluster.from_message(request.cluster) if request.HasField("cluster") else None

        api_connection = request.api_connection if request.HasField("api_connection") else None
        api_url = api_connection.url if api_connection and api_connection.url else None
        api_token = api_connection.token if api_connection and api_connection.token else None

        client = Client(url=api_url, token=api_token, client_id=runner_id)
        tracer = client._tracer  # noqa: SLF001
        task_logger = client._task_logger  # noqa: SLF001

        # Stage 2: older CLIs supply API credentials in InitializeWorker rather than
        # startup environment variables. This is a no-op if stage 1 already ran.
        # As of October 2026, keep this fallback for a few months; remove it once
        # deployed CLIs all provide startup credentials.
        initialize_logging(**client._auth)  # noqa: SLF001

        context_type = runner.context or RunnerContext
        runner_context = context_type(tracer)
        runner_context.storage_locations = LazyStorageLocations(client, runner_context)

        self._executor = TaskExecutor(
            runner,
            runner.cache or NoCache(),
            tracer,
            task_logger,
            runner_context,
            cluster.slug if cluster is not None else "",
        )
        logger.debug(
            f"InitializeWorker RPC returning for runner_id={runner_id}, cluster={cluster.slug if cluster is not None else None!r}"
        )
        return worker_pb2.InitializeRunnerResponse()

    def ExecuteTask(  # noqa: N802
        self,
        request: core_pb2.Task,
        context: grpc.ServicerContext,
    ) -> worker_pb2.ExecuteTaskResponse:
        logger.debug("ExecuteTask RPC called")
        self._authorize(context)
        self._loaded_runner(context)
        with self._tasks:
            if self._stopping:
                context.abort(grpc.StatusCode.UNAVAILABLE, "Worker is shutting down")
            self._active_tasks += 1
        try:
            return self._execute_task(request)
        finally:
            with self._tasks:
                self._active_tasks -= 1
                self._tasks.notify_all()

    def _execute_task(self, request: core_pb2.Task) -> worker_pb2.ExecuteTaskResponse:
        task = Task.from_message(request)
        executor = self._executor
        if executor is None:
            failed_task = FailedTask.from_task_error(
                task,
                RuntimeError("Worker is not initialized"),
                was_workflow_error=False,
                progress_updates=[],
            )
            logger.debug(f"ExecuteTask RPC returning failed task for uninitialized worker, task_id={task.id}")
            return worker_pb2.ExecuteTaskResponse(failed_task=failed_task.to_message())

        result = executor.execute_task(task)
        if isinstance(result, ComputedTask):
            logger.debug(f"ExecuteTask RPC returning computed task, task_id={task.id}")
            return worker_pb2.ExecuteTaskResponse(computed_task=result.to_message())
        if isinstance(result, FailedTask):
            logger.debug(f"ExecuteTask RPC returning failed task, task_id={task.id}")
            return worker_pb2.ExecuteTaskResponse(failed_task=result.to_message())
        raise TypeError(f"Unexpected task execution result: {type(result)}")

    def WatchLogs(self, request: Empty, context: grpc.ServicerContext) -> Iterator[LogRecord]:  # noqa: ARG002, N802
        self._authorize(context)
        context.send_initial_metadata(())
        logs = self._logs
        if logs is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Local log streaming is unavailable")
            raise RuntimeError("Local log streaming is unavailable")
        try:
            yield from logs.subscribe(context.is_active)
        except RuntimeError as error:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, str(error))

    def ShutdownWorker(self, request: Empty, context: grpc.ServicerContext) -> Empty:  # noqa: ARG002, N802
        self._authorize(context)
        logger.debug("ShutdownWorker RPC called")
        with self._tasks:
            self._stopping = True
            while self._active_tasks:
                self._tasks.wait()
        self._shutdown()
        logger.debug("ShutdownWorker RPC returning")
        return Empty()
