import builtins
from typing import Any
from uuid import UUID

from google.protobuf.empty_pb2 import Empty
from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.uuid import uuid_to_uuid_message
from tilebox.workflows.data import StorageLocation, StorageLocationReference
from tilebox.workflows.storage_locations.data import StorageSubscriptionEvents
from tilebox.workflows.workflows.v1.storage_location_pb2 import (
    CreateStorageLocationRequest,
    ListStorageSubscriptionEventsRequest,
    UpdateStorageLocationRequest,
)
from tilebox.workflows.workflows.v1.storage_location_pb2_grpc import StorageLocationServiceStub


class StorageLocationService:
    def __init__(self, channel: Channel | Any) -> None:
        self.service = (
            with_pythonic_errors(StorageLocationServiceStub(channel)) if hasattr(channel, "unary_unary") else channel
        )

    def list(self) -> builtins.list[StorageLocation]:
        response = self.service.ListStorageLocations(Empty())
        return [StorageLocation.from_message(location) for location in response.locations]

    def get_by_id(self, storage_location_id: UUID) -> StorageLocation:
        return StorageLocation.from_message(self.service.GetStorageLocation(uuid_to_uuid_message(storage_location_id)))

    def create(self, name: str, reference: StorageLocationReference) -> StorageLocation:
        request = CreateStorageLocationRequest(name=name, reference=reference.to_message())
        return StorageLocation.from_message(self.service.CreateStorageLocation(request))

    def update(self, storage_location_id: UUID, name: str) -> StorageLocation:
        request = UpdateStorageLocationRequest(storage_location_id=uuid_to_uuid_message(storage_location_id), name=name)
        return StorageLocation.from_message(self.service.UpdateStorageLocation(request))

    def list_events(self, storage_location_id: UUID, page: Pagination) -> StorageSubscriptionEvents:
        request = ListStorageSubscriptionEventsRequest(
            storage_location_id=uuid_to_uuid_message(storage_location_id), page=page.to_message()
        )
        return StorageSubscriptionEvents.from_message(self.service.ListStorageSubscriptionEvents(request))
