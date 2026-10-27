from typing import TypeAlias
from uuid import UUID

from protobuf.wkt.google.protobuf.empty_pb import Empty

from _tilebox.uuid import must_uuid_to_uuid_message, uuid_to_uuid_message
from tilebox.query.pagination import Pagination
from tilebox.workflows.data import StorageLocation, StorageLocationReference
from tilebox.workflows.storage_locations.data import StorageSubscriptionEvents
from tilebox.workflows.v1.storage_location_connect import StorageLocationServiceClientSync
from tilebox.workflows.v1.storage_location_pb import (
    CreateStorageLocationRequest,
    ListStorageSubscriptionEventsRequest,
    UpdateStorageLocationRequest,
)

StorageLocationIDLike: TypeAlias = StorageLocation | UUID | str


class StorageLocationClient:
    def __init__(self, service: StorageLocationServiceClientSync) -> None:
        self._service = service

    def all(self) -> list[StorageLocation]:
        """List all available storage locations."""
        response = self._service.list_storage_locations(Empty())
        return [StorageLocation.from_message(location) for location in response.locations]

    def find(self, storage_location_id: StorageLocationIDLike) -> StorageLocation:
        """Find a storage location by object, UUID, or UUID string."""
        return StorageLocation.from_message(
            self._service.get_storage_location(must_uuid_to_uuid_message(_to_uuid(storage_location_id)))
        )

    def create(self, name: str, reference: StorageLocationReference) -> StorageLocation:
        """Create a storage location from an AWS S3, GCS, Azure Blob, or local reference.

        Creating a location does not create the underlying bucket, container, or directory,
        or configure an event subscription.
        """
        return StorageLocation.from_message(
            self._service.create_storage_location(
                CreateStorageLocationRequest(name=name, reference=reference.to_message())
            )
        )

    def update(self, storage_location_id: StorageLocationIDLike, name: str) -> StorageLocation:
        """Rename a storage location. Its storage reference cannot be changed."""
        return StorageLocation.from_message(
            self._service.update_storage_location(
                UpdateStorageLocationRequest(
                    storage_location_id=uuid_to_uuid_message(_to_uuid(storage_location_id)), name=name
                )
            )
        )

    def list_events(self, storage_location_id: StorageLocationIDLike, page: Pagination) -> StorageSubscriptionEvents:
        """Fetch one page of storage subscription events and its continuation cursor."""
        request = ListStorageSubscriptionEventsRequest(
            storage_location_id=uuid_to_uuid_message(_to_uuid(storage_location_id)), page=page.to_message()
        )
        return StorageSubscriptionEvents.from_message(self._service.list_storage_subscription_events(request))


def _to_uuid(location: StorageLocationIDLike) -> UUID:
    if isinstance(location, StorageLocation):
        return location.id
    return UUID(location) if isinstance(location, str) else location
