from collections.abc import Callable

import grpc
from google.protobuf.empty_pb2 import Empty

from tilebox.workflows.data import ComputedTask, FailedTask, Task
from tilebox.workflows.runner.executor import TaskExecutor
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.runtime import RunnerRuntime
from tilebox.workflows.workflows.v1 import core_pb2, worker_pb2, worker_pb2_grpc


class WorkerServiceServicer(worker_pb2_grpc.WorkerServiceServicer):
    def __init__(
        self,
        runner: Runner,
        runtime: RunnerRuntime,
        executor: TaskExecutor,
        shutdown: Callable[[], None],
    ) -> None:
        self._runner = runner
        self._runtime = runtime
        self._executor = executor
        self._shutdown = shutdown
        self._initialized = False

    def ListRegisteredTasks(self, request: Empty, context: grpc.ServicerContext) -> core_pb2.TaskIdentifiers:  # noqa: ARG002, N802
        return core_pb2.TaskIdentifiers(
            identifiers=[identifier.to_message() for identifier in self._runner.task_identifiers]
        )

    def InitializeWorker(  # noqa: N802
        self,
        request: worker_pb2.InitializeRunnerRequest,
        context: grpc.ServicerContext,  # noqa: ARG002
    ) -> worker_pb2.InitializeRunnerResponse:
        self._runtime.initialize(request)
        self._initialized = True
        return worker_pb2.InitializeRunnerResponse()

    def ExecuteTask(  # noqa: N802
        self, request: core_pb2.Task, context: grpc.ServicerContext
    ) -> worker_pb2.ExecuteTaskResponse:
        if not self._initialized:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Worker has not been initialized")

        result = self._executor.execute(Task.from_message(request))
        if isinstance(result, ComputedTask):
            return worker_pb2.ExecuteTaskResponse(computed_task=result.to_message())
        if isinstance(result, FailedTask):
            return worker_pb2.ExecuteTaskResponse(failed_task=result.to_message())
        raise TypeError(f"Unexpected task execution result: {type(result)}")

    def ShutdownWorker(self, request: Empty, context: grpc.ServicerContext) -> Empty:  # noqa: ARG002, N802
        self._shutdown()
        return Empty()
