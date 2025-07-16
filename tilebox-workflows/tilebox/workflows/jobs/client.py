from typing import Any, TypeAlias
from uuid import UUID

from _tilebox.grpc.pagination import Pagination as PaginationProtocol
from _tilebox.grpc.pagination import paginated_request
from tilebox.datasets.query.id_interval import IDInterval, IDIntervalLike
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.query.time_interval import TimeInterval, TimeIntervalLike
from tilebox.workflows.clusters.client import ClusterSlugLike, to_cluster_slug
from tilebox.workflows.data import (
    Job,
    QueryFilters,
    QueryJobsResponse,
)
from tilebox.workflows.jobs.service import JobService
from tilebox.workflows.observability.tracing import WorkflowTracer, get_trace_parent_of_current_span
from tilebox.workflows.task import FutureTask
from tilebox.workflows.task import Task as TaskInstance

try:
    from IPython.display import HTML, display  # type: ignore[assignment]
except ImportError:

    class HTML:
        def __init__(*_args: Any, **_kwargs: Any) -> None: ...

    def display(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("IPython is not available. Diagram can only be displayed in a notebook.")


JobIDLike: TypeAlias = Job | UUID | str


class JobClient:
    def __init__(self, service: JobService, tracer: WorkflowTracer | None = None) -> None:
        """Create a new job client.

        Args:
            service: The service to use for job operations.
            tracer: The tracer to use for tracing.
        """
        self._service = service
        self._tracer = tracer or WorkflowTracer()

    def submit(
        self,
        job_name: str,
        root_task_or_tasks: TaskInstance | list[TaskInstance],
        cluster: ClusterSlugLike | list[ClusterSlugLike] | None = None,
        max_retries: int = 0,
    ) -> Job:
        """Submit a new job with the given root task(s).

        Args:
            job_name: The name of the job to submit.
            root_task_or_tasks: The root task(s) for the job to submit.
            cluster: The cluster to submit the root task of the given job to. If multiple root tasks are given, a list
                of clusters can be provided as well, specifying the cluster for each root task. If not provided, the default
                cluster will be used.
            max_retries: The maximum number of retries for the root task(s) in case of failure. Defaults to 0.

        Returns:
            The job that was submitted.
        """
        tasks = root_task_or_tasks if isinstance(root_task_or_tasks, list) else [root_task_or_tasks]

        if isinstance(cluster, ClusterSlugLike | None):
            slugs = [to_cluster_slug(cluster or "")] * len(tasks)
        else:
            slugs = [to_cluster_slug(c) for c in cluster]

        if len(tasks) != len(slugs):
            raise ValueError(
                f"Mismatch in number of provided clusters and tasks. Expected either one cluster to use for each task, "
                f"or exactly one cluster per task. But got {len(tasks)} tasks and {len(slugs)} clusters."
            )

        task_submissions = [
            FutureTask(i, task, [], slugs[i], max_retries).to_submission() for i, task in enumerate(tasks)
        ]

        with self._tracer.start_as_current_span(f"job/{job_name}"):
            trace_parent = get_trace_parent_of_current_span()
            return self._service.submit(job_name, trace_parent, task_submissions)

    def retry(self, job_or_id: JobIDLike) -> int:
        """Retry a job.

        Args:
            job: The job or job id to retry.

        Returns:
            Number of tasks that were retried.
        """
        # in case we only get an ID we fetch the job here, since we need the traceparent in order to start a span
        job = self.find(_to_uuid(job_or_id)) if not isinstance(job_or_id, Job) else job_or_id

        with self._tracer.start_job_span(job, "retry_job") as span:
            num_rescheduled = self._service.retry(job.id)
            span.add_event("retried_succeeded", {"num_tasks_rescheduled": num_rescheduled})
            return num_rescheduled

    def cancel(self, job_or_id: JobIDLike) -> None:
        """Cancel a job.

        Args:
            job: The job to cancel.
        """
        # in case we only get an ID we fetch the job here, since we need the traceparent in order to start a span
        job = self.find(_to_uuid(job_or_id)) if not isinstance(job_or_id, Job) else job_or_id

        with self._tracer.start_job_span(job, "cancel_job") as cancel_job:
            self._service.cancel(job.id)
            cancel_job.add_event("cancel_succeeded")

    def find(self, job_id: JobIDLike) -> Job:
        """Find a job by id.

        Args:
            job_id: The ID of the job to find. Can also be an existing job object, in which case this method acts
                as a refresh operation to fetch the latest job details.

        Returns:
            The job details for the given job_id.
        """
        return self._service.get_by_id(_to_uuid(job_id))

    def display(self, job: JobIDLike, direction: str = "down", layout: str = "dagre", sketchy: bool = True) -> None:
        """Create a visualization of the job as a diagram and display it in an interactive environment.

        Requires an IPython environment such as a Jupyter notebook.

        Args:
            job: The job or job id to visualize.
            direction: The direction of the diagram. Defaults to "down". See https://d2lang.com/tour/layouts/#direction
            layout: The layout to use for the diagram. Defaults to "dagre". Currently supported layouts are
                "dagre" and "elk". See https://d2lang.com/tour/layouts/
            sketchy: Whether to render the diagram in a sketchy hand drawn style. Defaults to True.
        """
        display(HTML(self.visualize(job, direction, layout, sketchy)))

    def visualize(self, job: JobIDLike, direction: str = "down", layout: str = "dagre", sketchy: bool = True) -> str:
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
        return self._service.visualize(_to_uuid(job), direction, layout, sketchy)

    def query(self, temporal_extent: TimeIntervalLike | IDIntervalLike, automation_id: UUID | None = None) -> list[Job]:
        """List jobs in the given temporal extent.

        Args:
            temporal_extent: The temporal extent to filter jobs by. If an IDInterval is given, jobs are filtered by their
                job id instead of their creation time.
                Can be specified in a number of ways:
                - TimeInterval: interval -> Use the time interval as its given
                - DatetimeScalar: [time, time] -> Construct a TimeInterval with start and end time set to the given
                    value and the end time inclusive
                - tuple of two DatetimeScalar: [start, end) -> Construct a TimeInterval with the given start and
                    end time
                - IDInterval: interval -> Use the ID interval as its given
                - tuple of two UUIDs: [start, end) -> Construct an IDInterval with the given start and end id
                - tuple of two strings: [start, end) -> Construct an IDInterval with the given start and end id
                    parsed from the strings
            automation_id: The automation id to filter jobs by. If specified, only jobs created by the given automation
                are returned.

        Returns:
            A list of jobs.
        """
        time_interval: TimeInterval | None = None
        id_interval: IDInterval | None = None
        match temporal_extent:
            case (str(), str()):
                # this is either a tuple of datetimes or a tuple of UUIDs
                try:
                    id_interval = IDInterval.parse(temporal_extent)
                except ValueError:
                    dataset_time_interval = TimeInterval.parse(temporal_extent)
                    time_interval = TimeInterval(
                        start=dataset_time_interval.start,
                        end=dataset_time_interval.end,
                        start_exclusive=dataset_time_interval.start_exclusive,
                        end_inclusive=dataset_time_interval.end_inclusive,
                    )
            case IDInterval(_, _, _, _) | (UUID(), UUID()):
                id_interval = IDInterval.parse(temporal_extent)
            case _:
                dataset_time_interval = TimeInterval.parse(temporal_extent)
                time_interval = TimeInterval(
                    start=dataset_time_interval.start,
                    end=dataset_time_interval.end,
                    start_exclusive=dataset_time_interval.start_exclusive,
                    end_inclusive=dataset_time_interval.end_inclusive,
                )

        filters = QueryFilters(time_interval=time_interval, id_interval=id_interval, automation_id=automation_id)

        def request(page: PaginationProtocol) -> QueryJobsResponse:
            query_page = Pagination(page.limit, page.starting_after)
            return self._service.query(filters, query_page)

        initial_page = Pagination()
        pages = paginated_request(request, initial_page)

        jobs = []
        for page in pages:
            jobs.extend(page.jobs)
        return jobs


def _to_uuid(job_or_id: Job | UUID | str) -> UUID:
    if isinstance(job_or_id, Job):
        return job_or_id.id
    if isinstance(job_or_id, str):
        return UUID(job_or_id)
    return job_or_id
