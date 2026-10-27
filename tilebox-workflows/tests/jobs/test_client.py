from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, rule
from tests.tasks_data import jobs

from _tilebox.errors import NotFoundError
from tilebox.datasets.query.id_interval import IDInterval
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.query.time_interval import datetime_to_timestamp
from tilebox.datasets.uuid import uuid_message_to_optional_uuid
from tilebox.workflows.data import (
    Job,
    JobState,
    LogRecord,
    LogSeverity,
    LogSeverityLiteral,
    Span,
    uuid_message_to_uuid,
    uuid_to_uuid_message,
)
from tilebox.workflows.jobs.client import JobClient
from tilebox.workflows.observability.tracing import NoopWorkflowTracer
from tilebox.workflows.task import ExecutionContext, Task
from tilebox.workflows.v1.core_pb import Job as JobMessage
from tilebox.workflows.v1.core_pb import JobState as JobStateEnum
from tilebox.workflows.v1.diagram_pb import Diagram
from tilebox.workflows.v1.job_connect import JobServiceClientSync
from tilebox.workflows.v1.job_pb import (
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
from tilebox.workflows.v1.telemetry_pb import PaginatedLogsData, PaginatedSpansData


class DummyTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context


def test_query_logs_paginates() -> None:
    next_page_start = uuid4()
    log_records = [
        LogRecord(
            time=datetime.now(tz=UTC),
            severity_number=9,
            severity_text="INFO",
            body="first",
            trace_id=None,
            span_id=None,
            attributes={},
            runner_attributes={},
        ),
        LogRecord(
            time=datetime.now(tz=UTC),
            severity_number=9,
            severity_text="INFO",
            body="second",
            trace_id=None,
            span_id=None,
            attributes={},
            runner_attributes={},
        ),
    ]
    telemetry_service = MagicMock()
    telemetry_service.query_job_logs.side_effect = [
        PaginatedLogsData(
            resource_logs=[log_records[0].to_message()],
            next_page=Pagination(starting_after=next_page_start).to_message(),
        ),
        PaginatedLogsData(resource_logs=[log_records[1].to_message()]),
    ]
    job_client = JobClient(MagicMock(), telemetry_service, NoopWorkflowTracer())
    job_id = uuid4()

    logs = job_client.query_logs(job_id)

    assert logs == log_records
    assert list(logs.to_pandas()["body"]) == ["first", "second"]
    assert [
        uuid_message_to_optional_uuid(call.args[0].page.starting_after)
        for call in telemetry_service.query_job_logs.call_args_list
    ] == [
        None,
        next_page_start,
    ]


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (LogSeverity.WARNING, [LogSeverity.WARNING.value]),
        ("warning", [LogSeverity.WARNING.value]),
        ([LogSeverity.WARNING, LogSeverity.ERROR], [LogSeverity.WARNING.value, LogSeverity.ERROR.value]),
        (["warning", "error"], [LogSeverity.WARNING.value, LogSeverity.ERROR.value]),
    ],
)
def test_query_logs_filters_by_task_and_severity(
    level: LogSeverity | LogSeverityLiteral | list[LogSeverity] | list[LogSeverityLiteral], expected: list[int]
) -> None:
    service = MagicMock()
    service.query_job_logs.return_value = PaginatedLogsData()
    job_client = JobClient(MagicMock(), service, NoopWorkflowTracer())
    task_id = uuid4()

    job_client.query_logs(uuid4(), task_id=str(task_id), level=level)

    request = service.query_job_logs.call_args.args[0]
    assert uuid_message_to_uuid(request.task_id) == task_id
    assert list(request.filters.severity_levels) == expected


def test_query_spans_paginates() -> None:
    next_page_start = uuid4()
    spans = [
        Span(
            start_time=datetime.now(tz=UTC),
            end_time=datetime.now(tz=UTC),
            trace_id="00" * 16,
            span_id="00" * 8,
            parent_span_id=None,
            name="first",
            status_code="STATUS_CODE_UNSET",
            status_message="",
            attributes={},
            runner_attributes={},
            events=[],
        ),
        Span(
            start_time=datetime.now(tz=UTC),
            end_time=datetime.now(tz=UTC),
            trace_id="00" * 16,
            span_id="00" * 8,
            parent_span_id=None,
            name="second",
            status_code="STATUS_CODE_UNSET",
            status_message="",
            attributes={},
            runner_attributes={},
            events=[],
        ),
    ]
    telemetry_service = MagicMock()
    telemetry_service.query_job_spans.side_effect = [
        PaginatedSpansData(
            resource_spans=[spans[0].to_message()], next_page=Pagination(starting_after=next_page_start).to_message()
        ),
        PaginatedSpansData(resource_spans=[spans[1].to_message()]),
    ]
    job_client = JobClient(MagicMock(), telemetry_service, NoopWorkflowTracer())
    job_id = uuid4()

    queried_spans = job_client.query_spans(job_id)

    assert queried_spans == spans
    assert list(queried_spans.to_pandas()["name"]) == ["first", "second"]
    assert [
        uuid_message_to_optional_uuid(call.args[0].page.starting_after)
        for call in telemetry_service.query_job_spans.call_args_list
    ] == [
        None,
        next_page_start,
    ]


def test_query_spans_filters_by_task() -> None:
    service = MagicMock()
    service.query_job_spans.return_value = PaginatedSpansData()
    job_client = JobClient(MagicMock(), service, NoopWorkflowTracer())
    task_id = uuid4()

    job_client.query_spans(uuid4(), task_id=str(task_id))

    request = service.query_job_spans.call_args.args[0]
    assert uuid_message_to_uuid(request.task_id) == task_id


class MockJobService:
    """Store jobs in memory for client behavior tests."""

    def __init__(self) -> None:
        self.jobs: dict[UUID, JobMessage] = {}
        self.query_requests: list[QueryJobsRequest] = []

    def submit_job(self, req: SubmitJobRequest) -> JobMessage:
        job_id = uuid4()
        job = JobMessage(
            id=uuid_to_uuid_message(job_id),
            name=req.job_name,
            trace_parent=req.trace_parent,
            state=JobStateEnum.SUBMITTED,
            submitted_at=datetime_to_timestamp(datetime.now(tz=UTC)),
        )
        self.jobs[job_id] = job
        return job

    def get_job(self, req: GetJobRequest) -> JobMessage:
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        return self.jobs[job_id]

    def retry_job(self, req: RetryJobRequest) -> RetryJobResponse:
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        copy = JobMessage.from_binary(self.jobs[job_id].to_binary())
        copy.state = JobStateEnum.SUBMITTED
        self.jobs[job_id] = copy
        return RetryJobResponse(num_tasks_rescheduled=1)

    def cancel_job(self, req: CancelJobRequest) -> CancelJobResponse:
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        copy = JobMessage.from_binary(self.jobs[job_id].to_binary())
        copy.state = JobStateEnum.CANCELED
        self.jobs[job_id] = copy
        return CancelJobResponse()

    def visualize_job(self, req: VisualizeJobRequest) -> Diagram:
        job_id = uuid_message_to_uuid(req.job_id)
        if job_id not in self.jobs:
            raise NotFoundError(f"No such job: {job_id}")

        job = self.jobs[job_id]
        if job.state == JobStateEnum.CANCELED:
            return Diagram(svg=b"<svg><text>Job canceled</text></svg>")

        return Diagram(svg=b"<svg><text>Job queued</text></svg>")

    def query_jobs(self, req: QueryJobsRequest) -> QueryJobsResponse:
        self.query_requests.append(req)
        return QueryJobsResponse(jobs=list(self.jobs.values()))


def test_query_filters_by_clusters() -> None:
    mock_service = MockJobService()
    service = MagicMock(spec=JobServiceClientSync, wraps=mock_service)
    job_client = JobClient(service, MagicMock(), NoopWorkflowTracer())

    job_client.query((uuid4(), uuid4()), clusters=["cluster-a", "cluster-b"])

    filters = mock_service.query_requests[-1].filters
    assert filters is not None
    assert list(filters.cluster_slugs) == ["cluster-a", "cluster-b"]


@pytest.mark.parametrize("use_interval", [False, True])
def test_query_uuid_interval_preserves_bounds(use_interval: bool) -> None:
    mock_service = MockJobService()
    service = MagicMock(spec=JobServiceClientSync, wraps=mock_service)
    job_client = JobClient(service, MagicMock(), NoopWorkflowTracer())
    start, end = UUID(int=17), UUID(int=93)
    extent = IDInterval(start, end, start_exclusive=True, end_inclusive=False) if use_interval else (start, end)

    job_client.query(extent)

    filters = mock_service.query_requests[-1].filters
    assert filters is not None
    assert filters.id_interval is not None
    assert not filters.has_field("time_interval")
    assert uuid_message_to_uuid(filters.id_interval.start_id) == start
    assert uuid_message_to_uuid(filters.id_interval.end_id) == end
    assert filters.id_interval.start_exclusive is use_interval
    assert filters.id_interval.end_inclusive is not use_interval


def test_query_empty_cluster_list_applies_no_cluster_filter() -> None:
    mock_service = MockJobService()
    service = MagicMock(spec=JobServiceClientSync, wraps=mock_service)
    job_client = JobClient(service, MagicMock(), NoopWorkflowTracer())

    job_client.query((uuid4(), uuid4()), clusters=[])

    filters = mock_service.query_requests[-1].filters
    assert filters is not None
    assert list(filters.cluster_slugs) == []


def test_query_without_temporal_extent() -> None:
    mock_service = MockJobService()
    service = MagicMock(spec=JobServiceClientSync, wraps=mock_service)
    job_client = JobClient(service, MagicMock(), NoopWorkflowTracer())

    job_client.query(job_states=JobState.RUNNING)

    filters = mock_service.query_requests[-1].filters
    assert filters is not None
    assert not filters.has_field("time_interval")
    assert not filters.has_field("id_interval")


def test_query_rejects_empty_cluster_slug() -> None:
    service = MagicMock(spec=JobServiceClientSync, wraps=MockJobService())
    job_client = JobClient(service, MagicMock(), NoopWorkflowTracer())

    with pytest.raises(ValueError, match="explicit cluster slugs"):
        job_client.query((uuid4(), uuid4()), clusters="")


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
        service = MagicMock(spec=JobServiceClientSync, wraps=MockJobService())
        self.job_client = JobClient(service, MagicMock(), NoopWorkflowTracer())
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
        assert got.state == JobState.SUBMITTED

    @rule(job=cancelled_jobs)
    def get_canceled_job(self, job: Job) -> None:
        got = self.job_client.find(job.id)
        assert got.name == job.name
        assert got.state == JobState.CANCELED

    @rule(target=cancelled_jobs, job=consumes(queued_jobs))  # consumes -> remove from bundle afterwards
    def cancel_job(self, job: Job) -> Job:
        self.job_client.cancel(job.id)
        job = self.job_client.find(job.id)
        assert job.state == JobState.CANCELED
        return job

    @rule(target=queued_jobs, job=consumes(cancelled_jobs))  # consumes -> remove from bundle afterwards
    def retry_job(self, job: Job) -> Job:
        self.job_client.retry(job.id)
        job = self.job_client.find(job.id)
        assert job.state == JobState.SUBMITTED
        return job

    @rule()
    def list_jobs(self) -> None:
        jobs = self.job_client.query((uuid4(), uuid4()))  # dummy id interval
        assert len(jobs) == self.count_total_submitted


# make pytest pick up the test cases from the state machine
TestJobOperations = JobOperations.TestCase
