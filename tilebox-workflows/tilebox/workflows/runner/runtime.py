from dataclasses import dataclass
from uuid import UUID

from tilebox.datasets.uuid import uuid_message_to_uuid
from tilebox.workflows.cache import JobCache, NoCache
from tilebox.workflows.data import Cluster, RunnerContext, StorageLocation, Workflow
from tilebox.workflows.observability.logging import StructuredLogger
from tilebox.workflows.observability.tracing import NoopWorkflowTracer, WorkflowTracer
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.workflows.v1.worker_pb2 import InitializeRunnerRequest


@dataclass
class RunnerRuntime:
    cache: JobCache
    tracer: WorkflowTracer
    task_logger: StructuredLogger
    _context: RunnerContext
    runner_id: UUID | None = None
    trace_parent: str | None = None
    cluster: Cluster | None = None
    workflow: Workflow | None = None

    @property
    def context(self) -> RunnerContext:
        return self._context

    def initialize(self, request: InitializeRunnerRequest) -> None:
        self.runner_id = uuid_message_to_uuid(request.runner_id)
        self.trace_parent = request.trace_parent or None
        self.cluster = Cluster.from_message(request.cluster) if request.HasField("cluster") else None
        self.workflow = Workflow.from_message(request.workflow) if request.HasField("workflow") else None

        storage_locations = [StorageLocation.from_message(location) for location in request.locations]
        self._context.storage_locations = {
            location.id: location._with_runner_context(self._context)  # noqa: SLF001
            for location in storage_locations
        }


def create_runner_runtime(
    runner: Runner,
    *,
    tracer: WorkflowTracer | None = None,
    task_logger: StructuredLogger,
    storage_locations: list[StorageLocation] | None = None,
) -> RunnerRuntime:
    tracer = tracer or NoopWorkflowTracer()
    context_type = runner.context or RunnerContext
    context = context_type(tracer, storage_locations=storage_locations)
    return RunnerRuntime(
        cache=runner.cache or NoCache(),
        tracer=tracer,
        task_logger=task_logger,
        _context=context,
    )
