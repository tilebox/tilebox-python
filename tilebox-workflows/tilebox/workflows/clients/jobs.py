from typing import Any
from uuid import UUID

from grpc.aio import Channel

from _tilebox.grpc.aio.syncify import Syncifiable
from tilebox.workflows.clients.clusters import cluster_slug
from tilebox.workflows.data import (
    Cluster,
    Job,
    TaskSubmission,
    uuid_to_uuid_message,
)
from tilebox.workflows.observability.tracing import (
    WorkflowTracer,
    get_trace_parent_of_current_span,
)
from tilebox.workflows.task import FutureTask
from tilebox.workflows.task import Task as TaskInstance
from tilebox.workflows.workflowsv1.core_pb2 import Job as JobMessage
from tilebox.workflows.workflowsv1.diagram_pb2 import Diagram, RenderOptions
from tilebox.workflows.workflowsv1.job_pb2 import (
    CancelJobRequest,
    GetJobRequest,
    RetryJobRequest,
    RetryJobResponse,
    SubmitJobRequest,
    VisualizeJobRequest,
)
from tilebox.workflows.workflowsv1.job_pb2_grpc import JobServiceStub

try:
    from IPython.display import HTML, display  # type: ignore[assignment]
except ImportError:

    class HTML:
        def __init__(*_args: Any, **_kwargs: Any) -> None: ...

    def display(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("IPython is not available. Diagram can only be displayed in a notebook.")


class JobService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the JobServiceStub that provides a more pythonic interface and converts the protobuf messages
        to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = JobServiceStub(channel)

    async def submit(self, job_name: str, trace_parent: str, tasks: list[TaskSubmission]) -> Job:
        """Submit a new job to the processing service.

        Args:
            job_name: The name of the job to create.
            trace_parent: Tracing information for the job. This is used to propagate tracing information to
                the workers that execute the tasks of the job.
            tasks: The root tasks of the job to submit.

        Returns:
            The created job.
        """
        request = SubmitJobRequest(
            tasks=[task.to_message() for task in tasks],
            job_name=job_name,
            trace_parent=trace_parent,
        )
        response: JobMessage = await self.service.SubmitJob(request)
        return Job.from_message(response)

    async def get_by_id(self, job_id: UUID) -> Job:
        """Fetch job details of a job by its id.

        Args:
            job_id: The UUID of the job to fetch.

        Returns:
            The job details for the given job_id.
        """
        request = GetJobRequest(job_id=uuid_to_uuid_message(job_id))
        response: JobMessage = await self.service.GetJob(request)
        return Job.from_message(response)

    async def retry(self, job_id: UUID) -> int:
        """Retry a job.

        Args:
            job_id: The UUID of the job to retry.

        Returns:
            Number of failed tasks that were retried.
        """
        request = RetryJobRequest(job_id=uuid_to_uuid_message(job_id))
        response: RetryJobResponse = await self.service.RetryJob(request)
        return response.num_tasks_rescheduled

    async def cancel(self, job_id: UUID) -> None:
        """Cancel a job.

        Args:
            job_id: The UUID of the job to cancel.
        """
        request = CancelJobRequest(job_id=uuid_to_uuid_message(job_id))
        await self.service.CancelJob(request)

    async def visualize(self, job_id: UUID, direction: str, layout: str = "dagre", sketchy: bool = True) -> str:
        """Render a d2 diagram of a job.

        Args:
            job_id: The UUID of the job to create a diagram for.
            direction: The direction of the diagram. Defaults to "down". See https://d2lang.com/tour/layouts/#direction
            layout: The layout to use for the diagram. Defaults to "dagre". Currently supported layouts are
                "dagre" and "elk". See https://d2lang.com/tour/layouts/
            sketchy: Whether to render the diagram in a sketchy hand drawn style. Defaults to True.

        Returns:
            Rendered SVG of the diagram.
        """
        request = VisualizeJobRequest(
            job_id=uuid_to_uuid_message(job_id),
            render_options=RenderOptions(sketchy=sketchy, padding=5, layout=layout, direction=direction),
        )
        response: Diagram = await self.service.VisualizeJob(request)
        return response.svg.decode("utf-8")


class JobClient(Syncifiable):
    def __init__(self, service: JobService, tracer: WorkflowTracer | None = None) -> None:
        """Create a new job client.

        Args:
            service: The service to use for job operations.
            tracer: The tracer to use for tracing.
        """
        self._service = service
        self._tracer = tracer or WorkflowTracer()

    async def submit(
        self,
        job_name: str,
        root_task_or_tasks: TaskInstance | list[TaskInstance],
        cluster: Cluster | str,
        max_retries: int = 0,
    ) -> Job:
        """Submit a new job with the given root task(s).

        Args:
            job_name: The name of the job to submit.
            root_task_or_tasks: The root task(s) for the job to submit.
            cluster: The cluster to submit the job to.
            max_retries: The maximum number of retries for the root task(s) in case of failure. Defaults to 0.

        Returns:
            The job that was submitted.
        """
        slug = cluster_slug(cluster)
        tasks = root_task_or_tasks if isinstance(root_task_or_tasks, list) else [root_task_or_tasks]

        task_submissions = [FutureTask(i, task, [], slug, max_retries).to_submission() for i, task in enumerate(tasks)]

        with self._tracer.start_as_current_span(f"job/{job_name}"):
            trace_parent = get_trace_parent_of_current_span()
            return await self._service.submit(job_name, trace_parent, task_submissions)

    async def retry(self, job: Job) -> int:
        """Retry a job.

        Args:
            job: The job to retry.

        Returns:
            Number of tasks that were retried.
        """
        with self._tracer.start_job_span(job, "retry_job") as span:
            num_rescheduled = await self._service.retry(job.id)
            span.add_event("retried_succeeded", {"num_tasks_rescheduled": num_rescheduled})
            return num_rescheduled

    async def cancel(self, job: Job) -> None:
        """Cancel a job.

        Args:
            job: The job to cancel.
        """
        with self._tracer.start_job_span(job, "cancel_job") as cancel_job:
            await self._service.cancel(job.id)
            cancel_job.add_event("cancel_succeeded")

    async def find(self, job_id: UUID | str) -> Job:
        """Find a job by id.

        Args:
            job_id: The job to find.

        Returns:
            The job details for the given job_id.
        """
        if isinstance(job_id, str):
            job_id = UUID(job_id)
        return await self._service.get_by_id(job_id)

    async def display(
        self, job: Job | UUID | str, direction: str = "down", layout: str = "dagre", sketchy: bool = True
    ) -> None:
        """Create a visualization of the job as a diagram and display it in an interactive environment.

        Requires an IPython environment such as a Jupyter notebook.

        Args:
            job: The job or job id to visualize.
            direction: The direction of the diagram. Defaults to "down". See https://d2lang.com/tour/layouts/#direction
            layout: The layout to use for the diagram. Defaults to "dagre". Currently supported layouts are
                "dagre" and "elk". See https://d2lang.com/tour/layouts/
            sketchy: Whether to render the diagram in a sketchy hand drawn style. Defaults to True.
        """
        diagram = await self._visualize(job, direction, layout, sketchy)
        display(HTML(diagram))

    async def visualize(
        self, job: Job | UUID | str, direction: str = "down", layout: str = "dagre", sketchy: bool = True
    ) -> str:
        """Create a visualization of the job as a diagram.

        Args:
            job: The job or job id to visualize.
            direction: The direction of the diagram. Defaults to "down". See https://d2lang.com/tour/layouts/#direction
            layout: The layout to use for the diagram. Defaults to "dagre". Currently supported layouts are
                "dagre" and "elk". See https://d2lang.com/tour/layouts/
            sketchy: Whether to render the diagram in a sketchy hand drawn style. Defaults to True.

        Returns:
            Rendered SVG of the diagram.
        """
        return await self._visualize(job, direction, layout, sketchy)

    async def _visualize(
        self, job: Job | UUID | str, direction: str = "down", layout: str = "dagre", sketchy: bool = True
    ) -> str:
        # implemented as a separate, private method, so that we can use it in both display and visualize
        # as async function, even if the client gets syncified
        job_id = job.id if isinstance(job, Job) else job
        if isinstance(job_id, str):
            job_id = UUID(job_id)
        return await self._service.visualize(job_id, direction, layout, sketchy)
