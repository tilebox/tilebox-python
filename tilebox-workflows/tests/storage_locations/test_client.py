from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from google.protobuf.empty_pb2 import Empty

from _tilebox.grpc.error import NotFoundError
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.query.time_interval import datetime_to_timestamp
from tilebox.datasets.tilebox.v1.id_pb2 import ID
from tilebox.datasets.tilebox.v1.query_pb2 import Pagination as PaginationMessage
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.workflows.data import (
    AWSS3BucketReference,
    AWSS3StorageLocation,
    AzureBlobReference,
    AzureBlobStorageLocation,
    GCSBucketReference,
    GCSStorageLocation,
    LocalReference,
    StorageEventType,
    StorageLocation,
    StorageLocationReference,
    StorageType,
)
from tilebox.workflows.storage_locations import StorageLocationClient
from tilebox.workflows.storage_locations.data import (
    StorageSubscriptionEvent,
    TriggeredJob,
)
from tilebox.workflows.storage_locations.service import StorageLocationService
from tilebox.workflows.workflows.v1 import storage_location_pb2 as storage_pb

_ID = UUID(int=1)
_OTHER_ID = UUID(int=2)
_ACCOUNT = "/subscriptions/example/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/account"


class MockStorageLocationService:
    def __init__(self) -> None:
        self.locations: dict[UUID, storage_pb.StorageLocation] = {}
        self.events: dict[UUID, list[storage_pb.StorageSubscriptionEvent]] = {}

    def CreateStorageLocation(self, request: storage_pb.CreateStorageLocationRequest) -> storage_pb.StorageLocation:  # noqa: N802
        location_id = UUID(int=len(self.locations) + 1)
        location = storage_pb.StorageLocation(
            id=uuid_to_uuid_message(location_id), name=request.name, reference=request.reference
        )
        self.locations[location_id] = location
        return location

    def GetStorageLocation(self, request: ID) -> storage_pb.StorageLocation:  # noqa: N802
        try:
            return self.locations[uuid_message_to_uuid(request)]
        except KeyError:
            raise NotFoundError("Unknown storage location") from None

    def ListStorageLocations(self, request: Empty) -> storage_pb.StorageLocations:  # noqa: N802, ARG002
        return storage_pb.StorageLocations(locations=self.locations.values())

    def UpdateStorageLocation(self, request: storage_pb.UpdateStorageLocationRequest) -> storage_pb.StorageLocation:  # noqa: N802
        location = self.GetStorageLocation(request.storage_location_id)
        location.name = request.name
        return location

    def ListStorageSubscriptionEvents(  # noqa: N802
        self, request: storage_pb.ListStorageSubscriptionEventsRequest
    ) -> storage_pb.StorageSubscriptionEvents:
        events = self.events.get(uuid_message_to_uuid(request.storage_location_id), [])
        if request.page.HasField("starting_after"):
            index = next(i for i, event in enumerate(events) if event.id == request.page.starting_after) + 1
            events = events[index:]
        limit = request.page.limit or len(events)
        return storage_pb.StorageSubscriptionEvents(
            events=events[:limit],
            next_page=PaginationMessage(limit=limit, starting_after=events[limit - 1].id)
            if len(events) > limit
            else None,
        )


@pytest.mark.parametrize(
    ("reference", "expected", "expected_string"),
    [
        (
            AWSS3BucketReference("s3-bucket", region="eu-west-2"),
            AWSS3StorageLocation(_ID, "s3-bucket", StorageType.AWS_S3, name="Source", region="eu-west-2"),
            "s3://s3-bucket",
        ),
        (
            GCSBucketReference("gcs-bucket", project_id="project", location="EU"),
            GCSStorageLocation(
                _ID, "gcs-bucket", StorageType.GCS, name="Source", project_id="project", bucket_location="EU"
            ),
            "gs://gcs-bucket",
        ),
        (
            AzureBlobReference(_ACCOUNT, "container", region="westeurope"),
            AzureBlobStorageLocation(
                _ID,
                "container",
                StorageType.AZURE_BLOB,
                name="Source",
                storage_account_resource_id=_ACCOUNT,
                region="westeurope",
            ),
            f"{_ACCOUNT}/containers/container",
        ),
        (
            LocalReference("/data/source"),
            StorageLocation(_ID, "/data/source", StorageType.LOCAL, name="Source"),
            "/data/source",
        ),
    ],
)
def test_storage_location_operations(
    reference: StorageLocationReference, expected: StorageLocation, expected_string: str
) -> None:
    client = StorageLocationClient(StorageLocationService(MockStorageLocationService()))
    assert client.all() == []
    created = client.create("Source", reference)
    other = client.create("Other", LocalReference("/data/other"))
    assert created == expected
    assert str(created) == expected_string
    message = created.to_message()
    assert message.location == ""
    assert message.type == storage_pb.STORAGE_TYPE_UNSPECIFIED
    assert StorageLocation.from_message(message) == expected
    message.location = "ignored-legacy-location"
    message.type = storage_pb.STORAGE_TYPE_LOCAL if expected.type != StorageType.LOCAL else storage_pb.STORAGE_TYPE_GCS
    assert StorageLocation.from_message(message) == expected
    assert client.all() == [expected, other]
    for identifier in (created, created.id, str(created.id)):
        assert client.find(identifier) == expected
        assert client.update(identifier, "Renamed") == replace(expected, name="Renamed")
        assert client.find(other).name == "Other"
        assert client.update(identifier, "Source") == expected
    with pytest.raises(NotFoundError, match="Unknown storage location"):
        client.find(UUID(int=99))


def test_storage_location_requires_reference() -> None:
    message = storage_pb.StorageLocation(
        id=uuid_to_uuid_message(_ID), location="legacy-bucket", type=storage_pb.STORAGE_TYPE_AWS_S3
    )
    with pytest.raises(ValueError, match="Unsupported storage reference type"):
        StorageLocation.from_message(message)


def test_storage_event_service_returns_one_page_and_cursor() -> None:
    service = MockStorageLocationService()
    storage_service = StorageLocationService(service)
    event_time = datetime(2026, 10, 7, 12, 34, 56, 123456, tzinfo=UTC)
    received_at = datetime(2026, 10, 8, 1, 2, 3, 654321, tzinfo=UTC)
    service.events[_ID] = [
        storage_pb.StorageSubscriptionEvent(
            id=uuid_to_uuid_message(UUID(int=10)),
            object_key="nested/first.txt",
            type=storage_pb.STORAGE_EVENT_TYPE_CREATED,
            event_time=datetime_to_timestamp(event_time),
            received_at=datetime_to_timestamp(received_at),
            storage_subscription_id=uuid_to_uuid_message(UUID(int=20)),
            triggered_jobs=[
                storage_pb.TriggeredJob(
                    job_id=uuid_to_uuid_message(UUID(int=30)),
                    automation_id=uuid_to_uuid_message(UUID(int=40)),
                    glob_pattern="nested/*.txt",
                )
            ],
        ),
        storage_pb.StorageSubscriptionEvent(
            id=uuid_to_uuid_message(UUID(int=11)),
            object_key="second.bin",
            type=storage_pb.STORAGE_EVENT_TYPE_CREATED,
            event_time=datetime_to_timestamp(received_at),
            received_at=datetime_to_timestamp(received_at),
            storage_subscription_id=uuid_to_uuid_message(UUID(int=21)),
        ),
    ]
    expected = [
        StorageSubscriptionEvent(
            UUID(int=10),
            "nested/first.txt",
            StorageEventType.CREATED,
            event_time,
            received_at,
            [TriggeredJob(UUID(int=30), UUID(int=40), "nested/*.txt")],
            UUID(int=20),
        ),
        StorageSubscriptionEvent(
            UUID(int=11), "second.bin", StorageEventType.CREATED, received_at, received_at, [], UUID(int=21)
        ),
    ]
    first_page = storage_service.list_events(_ID, Pagination(limit=1))
    assert first_page.events == expected[:1]
    assert first_page.next_page == Pagination(limit=1, starting_after=UUID(int=10))
    second_page = storage_service.list_events(_ID, first_page.next_page)
    assert second_page.events == expected[1:]
    assert second_page.next_page == Pagination()
    assert storage_service.list_events(_OTHER_ID, Pagination()).events == []
