from uuid import UUID

from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.query.pagination import Pagination
from tilebox.workflows.data import (
    Job,
    QueryFilters,
    QueryJobsResponse,
    TaskSubmissions,
    uuid_to_uuid_message,
)
from tilebox.workflows.formatting.job import JobWidget, RichDisplayJob
from tilebox.workflows.workflows.v1.core_pb2 import Job as JobMessage
from tilebox.workflows.workflows.v1.diagram_pb2 import Diagram, RenderOptions
from tilebox.workflows.workflows.v1.job_pb2 import (
    CancelJobRequest,
    GetJobProgressRequest,
    GetJobRequest,
    QueryJobsRequest,
    RetryJobRequest,
    RetryJobResponse,
    SubmitJobRequest,
    VisualizeJobRequest,
)
from tilebox.workflows.workflows.v1.job_pb2 import QueryJobsResponse as QueryJobsResponseMessage
from tilebox.workflows.workflows.v1.job_pb2_grpc import JobServiceStub


class JobService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the JobServiceStub that provides a more pythonic interface and converts the protobuf messages
        to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = with_pythonic_errors(JobServiceStub(channel))

    def submit(self, job_name: str, trace_parent: str, tasks: TaskSubmissions) -> Job:
        request = SubmitJobRequest(
            tasks=tasks.to_message(),
            job_name=job_name,
            trace_parent=trace_parent,
        )
        return RichDisplayJob.from_message(self.service.SubmitJob(request), _widget=JobWidget(self.get_progress))

    def get_by_id(self, job_id: UUID) -> Job:
        request = GetJobRequest(job_id=uuid_to_uuid_message(job_id))
        response: JobMessage = self.service.GetJob(request)
        return RichDisplayJob.from_message(response, _widget=JobWidget(self.get_progress))

    def get_progress(self, job_id: UUID) -> Job:
        request = GetJobProgressRequest(job_id=uuid_to_uuid_message(job_id))
        return Job.from_message(self.service.GetJobProgress(request))

    def retry(self, job_id: UUID) -> int:
        request = RetryJobRequest(job_id=uuid_to_uuid_message(job_id))
        response: RetryJobResponse = self.service.RetryJob(request)
        return response.num_tasks_rescheduled

    def cancel(self, job_id: UUID) -> None:
        request = CancelJobRequest(job_id=uuid_to_uuid_message(job_id))
        self.service.CancelJob(request)

    def visualize(self, job_id: UUID, direction: str, layout: str = "dagre", sketchy: bool = True) -> str:
        request = VisualizeJobRequest(
            job_id=uuid_to_uuid_message(job_id),
            render_options=RenderOptions(sketchy=sketchy, padding=5, layout=layout, direction=direction),
        )
        response: Diagram = self.service.VisualizeJob(request)
        return response.svg.decode("utf-8")

    def query(self, filters: QueryFilters, page: Pagination | None = None) -> QueryJobsResponse:
        request = QueryJobsRequest(
            filters=filters.to_message(),
            page=page.to_message() if page is not None else None,
        )
        response: QueryJobsResponseMessage = self.service.QueryJobs(request)

        return QueryJobsResponse.from_message(
            response, job_factory=lambda job: RichDisplayJob.from_message(job, _widget=JobWidget(self.get_progress))
        )
