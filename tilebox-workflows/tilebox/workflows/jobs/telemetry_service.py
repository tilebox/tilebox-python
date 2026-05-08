from uuid import UUID

from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.query.pagination import Pagination
from tilebox.workflows.data import (
    QueryJobLogsResponse,
    QueryJobSpansResponse,
    uuid_to_uuid_message,
)
from tilebox.workflows.workflows.v1.telemetry_pb2 import (
    PaginatedLogsData,
    PaginatedSpansData,
    QueryJobLogsRequest,
    QueryJobSpansRequest,
)
from tilebox.workflows.workflows.v1.telemetry_pb2_grpc import TelemetryQueryServiceStub


class TelemetryService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the TelemetryQueryServiceStub that provides a more pythonic interface and converts the
        protobuf messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = with_pythonic_errors(TelemetryQueryServiceStub(channel))

    def query_job_logs(self, job_id: UUID, page: Pagination | None = None) -> QueryJobLogsResponse:
        request = QueryJobLogsRequest(
            job_id=uuid_to_uuid_message(job_id),
            page=page.to_message() if page is not None else None,
        )
        response: PaginatedLogsData = self.service.QueryJobLogs(request)
        return QueryJobLogsResponse.from_message(response)

    def query_job_spans(self, job_id: UUID, page: Pagination | None = None) -> QueryJobSpansResponse:
        request = QueryJobSpansRequest(
            job_id=uuid_to_uuid_message(job_id),
            page=page.to_message() if page is not None else None,
        )
        response: PaginatedSpansData = self.service.QueryJobSpans(request)
        return QueryJobSpansResponse.from_message(response)
