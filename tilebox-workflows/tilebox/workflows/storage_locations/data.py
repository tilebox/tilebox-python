from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.query.time_interval import timestamp_to_datetime
from tilebox.datasets.uuid import uuid_message_to_uuid
from tilebox.workflows.data import StorageEventType
from tilebox.workflows.workflows.v1 import storage_location_pb2 as storage_pb


@dataclass(frozen=True)
class TriggeredJob:
    job_id: UUID
    automation_id: UUID
    glob_pattern: str

    @classmethod
    def from_message(cls, job: storage_pb.TriggeredJob) -> "TriggeredJob":
        return cls(
            job_id=uuid_message_to_uuid(job.job_id),
            automation_id=uuid_message_to_uuid(job.automation_id),
            glob_pattern=job.glob_pattern,
        )


@dataclass(frozen=True)
class StorageSubscriptionEvent:
    id: UUID
    object_key: str
    type: StorageEventType
    event_time: datetime
    received_at: datetime
    triggered_jobs: list[TriggeredJob]
    storage_subscription_id: UUID

    @classmethod
    def from_message(cls, event: storage_pb.StorageSubscriptionEvent) -> "StorageSubscriptionEvent":
        return cls(
            id=uuid_message_to_uuid(event.id),
            object_key=event.object_key,
            type=StorageEventType(event.type),
            event_time=timestamp_to_datetime(event.event_time),
            received_at=timestamp_to_datetime(event.received_at),
            triggered_jobs=[TriggeredJob.from_message(job) for job in event.triggered_jobs],
            storage_subscription_id=uuid_message_to_uuid(event.storage_subscription_id),
        )


@dataclass(frozen=True)
class StorageSubscriptionEvents:
    events: list[StorageSubscriptionEvent]
    next_page: Pagination

    @classmethod
    def from_message(cls, page: storage_pb.StorageSubscriptionEvents) -> "StorageSubscriptionEvents":
        return cls(
            events=[StorageSubscriptionEvent.from_message(event) for event in page.events],
            next_page=Pagination.from_message(page.next_page),
        )
