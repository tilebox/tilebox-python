from typing import Any, cast
from uuid import UUID

from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.query.pagination import Pagination
from tilebox.workflows.data import (
    LogSeverity,
    QueryJobLogsResponse,
    QueryJobSpansResponse,
    uuid_to_uuid_message,
)
from tilebox.workflows.workflows.v1 import telemetry_pb2
from tilebox.workflows.workflows.v1.telemetry_pb2 import (
    LogQueryFilters,
    PaginatedLogsData,
    PaginatedSpansData,
    QueryJobLogsRequest,
    QueryJobSpansRequest,
)
from tilebox.workflows.workflows.v1.telemetry_pb2_grpc import TelemetryQueryServiceStub


class TelemetryService:
    def __init__(self, channel: Channel | Any) -> None:
        """
        A wrapper around the TelemetryQueryServiceStub that provides a more pythonic interface and converts the
        protobuf messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = (
            with_pythonic_errors(TelemetryQueryServiceStub(channel)) if hasattr(channel, "unary_unary") else channel
        )

    def query_job_logs(
        self,
        job_id: UUID,
        page: Pagination | None = None,
        task_id: UUID | None = None,
        severity_levels: list[LogSeverity] | None = None,
    ) -> QueryJobLogsResponse:
        request = QueryJobLogsRequest(
            job_id=uuid_to_uuid_message(job_id),
            page=page.to_message() if page is not None else None,
            task_id=uuid_to_uuid_message(task_id) if task_id is not None else None,
            filters=LogQueryFilters(
                severity_levels=[cast(telemetry_pb2.LogSeverityGroup, severity.value) for severity in severity_levels]
            )
            if severity_levels
            else None,
        )
        response: PaginatedLogsData = self.service.QueryJobLogs(request)
        return QueryJobLogsResponse.from_message(response)

    def query_job_spans(
        self, job_id: UUID, page: Pagination | None = None, task_id: UUID | None = None
    ) -> QueryJobSpansResponse:
        request = QueryJobSpansRequest(
            job_id=uuid_to_uuid_message(job_id),
            page=page.to_message() if page is not None else None,
            task_id=uuid_to_uuid_message(task_id) if task_id is not None else None,
        )
        response: PaginatedSpansData = self.service.QueryJobSpans(request)
        return QueryJobSpansResponse.from_message(response)
