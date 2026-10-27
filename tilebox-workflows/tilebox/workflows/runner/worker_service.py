import asyncio
import hmac
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing, suppress
from typing import TypeVar

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.request import RequestContext
from protobuf.wkt.google.protobuf.empty_pb import Empty

from _tilebox.uuid import uuid_message_to_uuid
from tilebox.workflows._otel.opentelemetry.proto.logs.v1.logs_pb import LogRecord
from tilebox.workflows.cache import NoCache
from tilebox.workflows.client import Client
from tilebox.workflows.data import Cluster, ComputedTask, FailedTask, Task
from tilebox.workflows.observability._log_stream import _LogQueue
from tilebox.workflows.observability._logging import logger
from tilebox.workflows.observability.logging import initialize_logging
from tilebox.workflows.runner.executor import LazyStorageLocations, TaskExecutor
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.task import RunnerContext
from tilebox.workflows.v1 import core_pb, worker_pb
from tilebox.workflows.v1.worker_connect import WorkerService

_Result = TypeVar("_Result")


async def _offload(function: Callable[[], _Result]) -> _Result:
    """Run blocking user code without pinning process exit after the shutdown deadline."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[_Result] = loop.create_future()

    def complete(result: _Result | None, error: BaseException | None) -> None:
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        else:
            future.set_result(result)  # ty: ignore[invalid-argument-type]

    def run() -> None:
        result, error = None, None
        try:
            result = function()
        except BaseException as caught:  # noqa: BLE001 -- propagate user failures to the request
            error = caught
        # The bounded shutdown deadline may already have closed the loop.
        with suppress(RuntimeError):
            loop.call_soon_threadsafe(complete, result, error)

    threading.Thread(target=run, name="tilebox-worker-task", daemon=True).start()
    return await future


class WorkerServiceServicer(WorkerService):
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
        self._initialize_lock = threading.Lock()

    def _authorize(self, context: RequestContext) -> None:
        if self._token is None:
            return
        supplied = context.request_headers.get("authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {self._token}"):
            raise ConnectError(Code.UNAUTHENTICATED, "Invalid runtime authorization")

    def set_runner(self, runner: Runner) -> None:
        self._runner = runner

    def _loaded_runner(self, context: RequestContext) -> Runner:  # noqa: ARG002
        runner = self._runner
        if runner is None:
            raise ConnectError(Code.UNAVAILABLE, "Worker runtime is still loading")
        return runner

    async def list_registered_tasks(self, request: Empty, context: RequestContext) -> core_pb.UnboundTaskIdentifiers:  # noqa: ARG002
        logger.debug("ListRegisteredTasks RPC called")
        self._authorize(context)
        runner = self._loaded_runner(context)
        identifiers = [identifier.to_message() for identifier in runner.task_identifiers]
        logger.debug(f"ListRegisteredTasks RPC returning {len(identifiers)} task identifier(s)")
        return core_pb.UnboundTaskIdentifiers(identifiers=identifiers)

    async def initialize_worker(
        self, request: worker_pb.InitializeRunnerRequest, context: RequestContext
    ) -> worker_pb.InitializeRunnerResponse:
        self._authorize(context)
        return await _offload(lambda: self._initialize_worker(request, context))

    def _initialize_worker(
        self,
        request: worker_pb.InitializeRunnerRequest,
        context: RequestContext,
    ) -> worker_pb.InitializeRunnerResponse:
        with self._initialize_lock:
            return self._initialize(request, context)

    def _initialize(
        self,
        request: worker_pb.InitializeRunnerRequest,
        context: RequestContext,
    ) -> worker_pb.InitializeRunnerResponse:
        logger.debug("InitializeWorker RPC called")
        self._authorize(context)
        runner = self._loaded_runner(context)
        runner_id = uuid_message_to_uuid(request.runner_id)
        if self._executor is not None:
            raise ConnectError(Code.FAILED_PRECONDITION, "Worker is already initialized")
        cluster = Cluster.from_message(request.cluster) if request.cluster is not None else None

        api_connection = request.api_connection if request.has_field("api_connection") else None
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
        return worker_pb.InitializeRunnerResponse()

    async def execute_task(
        self,
        request: core_pb.Task,
        context: RequestContext,
    ) -> worker_pb.ExecuteTaskResponse:
        logger.debug("ExecuteTask RPC called")
        self._authorize(context)
        self._loaded_runner(context)
        with self._tasks:
            if self._stopping:
                raise ConnectError(Code.UNAVAILABLE, "Worker is shutting down")
            self._active_tasks += 1
        # Cancellation of the HTTP request must not orphan task cleanup.
        task = asyncio.create_task(_offload(lambda: self._execute_active_task(request)))
        return await asyncio.shield(task)

    def _execute_active_task(self, request: core_pb.Task) -> worker_pb.ExecuteTaskResponse:
        try:
            return self._execute_task(request)
        finally:
            with self._tasks:
                self._active_tasks -= 1
                self._tasks.notify_all()

    def _execute_task(self, request: core_pb.Task) -> worker_pb.ExecuteTaskResponse:
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
            return worker_pb.ExecuteTaskResponse(failed_task=failed_task.to_message())

        result = executor.execute_task(task)
        if isinstance(result, ComputedTask):
            logger.debug(f"ExecuteTask RPC returning computed task, task_id={task.id}")
            return worker_pb.ExecuteTaskResponse(computed_task=result.to_message())
        if isinstance(result, FailedTask):
            logger.debug(f"ExecuteTask RPC returning failed task, task_id={task.id}")
            return worker_pb.ExecuteTaskResponse(failed_task=result.to_message())
        raise TypeError(f"Unexpected task execution result: {type(result)}")

    async def watch_logs(self, request: Empty, context: RequestContext) -> AsyncIterator[LogRecord]:  # noqa: ARG002
        self._authorize(context)
        logs = self._logs
        if logs is None:
            raise ConnectError(Code.UNAVAILABLE, "Local log streaming is unavailable")
        try:
            async with aclosing(logs.subscribe_async()) as records:
                async for record in records:
                    yield record
        except RuntimeError as error:
            raise ConnectError(Code.ALREADY_EXISTS, str(error)) from error

    async def shutdown_worker(self, request: Empty, context: RequestContext) -> Empty:  # noqa: ARG002
        self._authorize(context)
        logger.debug("ShutdownWorker RPC called")
        with self._tasks:
            self._stopping = True
        return await asyncio.shield(asyncio.create_task(self._finish_shutdown()))

    async def _finish_shutdown(self) -> Empty:
        await asyncio.to_thread(self._wait_tasks)
        self._shutdown()
        logger.debug("ShutdownWorker RPC returning")
        return Empty()

    def _wait_tasks(self) -> None:
        with self._tasks:
            self._tasks.wait_for(lambda: self._active_tasks == 0, timeout=5)
