from typing import TypeAlias
from uuid import UUID

from tilebox.workflows.data import StorageLocation, StorageLocationReference
from tilebox.workflows.storage_locations.service import StorageLocationService

StorageLocationIDLike: TypeAlias = StorageLocation | UUID | str


class StorageLocationClient:
    def __init__(self, service: StorageLocationService) -> None:
        self._service = service

    def all(self) -> list[StorageLocation]:
        """List all available storage locations."""
        return self._service.list()

    def find(self, storage_location_id: StorageLocationIDLike) -> StorageLocation:
        """Find a storage location by object, UUID, or UUID string."""
        return self._service.get_by_id(_to_uuid(storage_location_id))

    def create(self, name: str, reference: StorageLocationReference) -> StorageLocation:
        """Create a storage location from an AWS S3, GCS, Azure Blob, or local reference.

        Creating a location does not create the underlying bucket, container, or directory,
        or configure an event subscription.
        """
        return self._service.create(name, reference)

    def update(self, storage_location_id: StorageLocationIDLike, name: str) -> StorageLocation:
        """Rename a storage location. Its storage reference cannot be changed."""
        return self._service.update(_to_uuid(storage_location_id), name)


def _to_uuid(location: StorageLocationIDLike) -> UUID:
    if isinstance(location, StorageLocation):
        return location.id
    return UUID(location) if isinstance(location, str) else location
