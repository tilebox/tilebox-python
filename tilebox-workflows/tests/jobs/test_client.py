from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, rule
from tests.tasks_data import jobs

from _tilebox.grpc.error import NotFoundError
from tilebox.datasets.data.time_interval import datetime_to_timestamp
from tilebox.workflows.data import Job, uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.workflows.jobs.client import JobClient
from tilebox.workflows.jobs.service import JobService
from tilebox.workflows.task import ExecutionContext, Task
from tilebox.workflows.workflowsv1.core_pb2 import Job as JobMessage
from tilebox.workflows.workflowsv1.core_pb2 import JobState
from tilebox.workflows.workflowsv1.diagram_pb2 import Diagram
from tilebox.workflows.workflowsv1.job_pb2 import (
    CancelJobRequest,
    CancelJobResponse,
    GetJobRequest,
    QueryJobsRequest,
    QueryJobsResponse,
    RetryJobRequest,
    RetryJobResponse,
    SubmitJobRequest,
    VisualizeJobRequest,
)
from tilebox.workflows.workflowsv1.job_pb2_grpc import JobServiceStub


class DummyTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context


class MockJobService(JobServiceStub):
    """A mock implementation of the gRPC job service, that stores jobs in memory as a dict."""

    def __init__(self) -> None:
        self.jobs: dict[UUID, JobMessage] = {}

    def SubmitJob(self, req: SubmitJobRequest) -> JobMessage:  # noqa: N802
        job_id = uuid4()
        job = JobMessage(
            id=uuid_to_uuid_message(job_id),
            name=req.job_name,
            trace_parent=req.trace_parent,
            canceled=False,
            state=JobState.JOB_STATE_QUEUED,
            submitted_at=datetime_to_timestamp(datetime.now(tz=timezone.utc)),
        )
        self.jobs[job_id] = job
        return job

    def GetJob(self, req: GetJobRequest) -> JobMessage:  # noqa: N802
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        return self.jobs[job_id]

    def RetryJob(self, req: RetryJobRequest) -> RetryJobResponse:  # noqa: N802
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        copy = JobMessage.FromString(self.jobs[job_id].SerializeToString())
        copy.canceled = False
        copy.state = JobState.JOB_STATE_QUEUED
        self.jobs[job_id] = copy
        return RetryJobResponse(num_tasks_rescheduled=1)

    def CancelJob(self, req: CancelJobRequest) -> CancelJobResponse:  # noqa: N802
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        copy = JobMessage.FromString(self.jobs[job_id].SerializeToString())
        copy.canceled = True
        copy.state = JobState.JOB_STATE_STARTED
        self.jobs[job_id] = copy
        return CancelJobResponse()

    def VisualizeJob(self, req: VisualizeJobRequest) -> Diagram:  # noqa: N802
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        job = self.jobs[job_id]
        if job.canceled:
            return Diagram(svg=b"<svg><text>Job canceled</text></svg>")

        return Diagram(svg=b"<svg><text>Job queued</text></svg>")

    def QueryJobs(self, req: QueryJobsRequest) -> QueryJobsResponse:  # noqa: N802
        _ = req
        return QueryJobsResponse(jobs=list(self.jobs.values()))


class JobOperations(RuleBasedStateMachine):
    """
    A state machine that tests the various job operations of the Jobs client.

    The rules defined here will be executed in random order by Hypothesis, and each rule can be called any number of
    times. The state of the state machine is defined by the bundles, which are collections of objects that can be
    inserted into the state machine by the rules. Rules can also consume objects from the bundles, which will remove
    them from the state machine state.

    For more information see:
    https://hypothesis.readthedocs.io/en/latest/stateful.html
    """

    def __init__(self) -> None:
        super().__init__()
        service = JobService(MagicMock())
        service.service = MockJobService()  # mock the gRPC service
        self.job_client = JobClient(service)
        self.count_total_submitted = 0

    queued_jobs: Bundle[Job] = Bundle("queued_jobs")
    cancelled_jobs: Bundle[Job] = Bundle("canceled_jobs")

    @rule(target=queued_jobs, job=jobs())
    def submit_job(self, job: Job) -> Job:
        self.count_total_submitted += 1
        return self.job_client.submit(job.name, DummyTask(), cluster="dummy-cluster")

    @rule(job=queued_jobs)
    def get_queued_job(self, job: Job) -> None:
        got = self.job_client.find(job.id)
        assert got.name == job.name
        assert not got.canceled

    @rule(job=cancelled_jobs)
    def get_canceled_job(self, job: Job) -> None:
        got = self.job_client.find(job.id)
        assert got.name == job.name
        assert got.canceled

    @rule(target=cancelled_jobs, job=consumes(queued_jobs))  # consumes -> remove from bundle afterwards
    def cancel_job(self, job: Job) -> Job:
        self.job_client.cancel(job.id)
        job = self.job_client.find(job.id)
        assert job.canceled
        return job

    @rule(target=queued_jobs, job=consumes(cancelled_jobs))  # consumes -> remove from bundle afterwards
    def retry_job(self, job: Job) -> Job:
        self.job_client.retry(job.id)
        job = self.job_client.find(job.id)
        assert not job.canceled
        return job

    @rule()
    def list_jobs(self) -> None:
        jobs = self.job_client.query((uuid4(), uuid4()))  # dummy id interval
        assert len(jobs) == self.count_total_submitted


# make pytest pick up the test cases from the state machine
TestJobOperations = JobOperations.TestCase
