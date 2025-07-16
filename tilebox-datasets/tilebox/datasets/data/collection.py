from dataclasses import dataclass
from uuid import UUID

from tilebox.datasets.datasets.v1 import core_pb2
from tilebox.datasets.query.time_interval import TimeInterval
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message


@dataclass
class Collection:
    """Basic properties of a collection of datapoints in a timeseries dataset."""

    id: UUID
    name: str

    @classmethod
    def from_message(cls, collection: core_pb2.Collection) -> "Collection":
        return Collection(id=uuid_message_to_uuid(collection.id), name=collection.name)

    def to_message(self) -> core_pb2.Collection:
        return core_pb2.Collection(id=uuid_to_uuid_message(self.id), name=self.name)


@dataclass
class CollectionInfo:
    """Metadata about the datapoints in a collection in a timeseries dataset."""

    collection: Collection
    availability: TimeInterval | None
    count: int | None

    @classmethod
    def from_message(cls, info: core_pb2.CollectionInfo) -> "CollectionInfo":
        """
        Convert a CollectionInfo protobuf message to a CollectionInfo object.

        Args:
            info: The protobuf message to convert
            availability_known: Whether the availability of the collection was requested or not.
                This is used to distinguish between a collection that has no data points and a collection for which we
                don't know whether it has data points or not. Because the protobuf message availability field is
                None for both of those cases.
        """
        return CollectionInfo(
            collection=Collection.from_message(info.collection),
            availability=TimeInterval.from_message(info.availability) if info.HasField("availability") else None,
            count=info.count if info.HasField("count") else None,
        )

    def to_message(self) -> core_pb2.CollectionInfo:
        info = core_pb2.CollectionInfo(collection=self.collection.to_message())
        if isinstance(self.availability, TimeInterval):
            info.availability.CopyFrom(self.availability.to_message())
        if self.count is not None:
            info.count = self.count
        return info

    def __str__(self) -> str:
        """Human readable representation of the collection info."""
        availability = "<availability unknown>" if self.availability is None else str(self.availability)
        count = "" if self.count is None else f" ({self.count} data points)"
        return f"{self.collection.name}: {availability}{count}"

    def __repr__(self) -> str:
        """Human readable representation of the collection info."""
        return f"Collection {self!s}"
