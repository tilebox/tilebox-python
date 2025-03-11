from dataclasses import dataclass, field
from uuid import UUID

from tilebox.datasets.data.pagination import Pagination
from tilebox.datasets.data.uuid import uuid_message_to_uuid
from tilebox.datasets.datasetsv1 import core_pb2, data_ingestion_pb2


@dataclass(frozen=True)
class DatapointInterval:
    start_id: str
    end_id: str
    start_exclusive: bool
    end_inclusive: bool

    @classmethod
    def from_message(cls, interval: core_pb2.DatapointInterval) -> "DatapointInterval":
        return cls(
            start_id=interval.start_id,
            end_id=interval.end_id,
            start_exclusive=interval.start_exclusive,
            end_inclusive=interval.end_inclusive,
        )

    def to_message(self) -> core_pb2.DatapointInterval:
        return core_pb2.DatapointInterval(
            start_id=self.start_id,
            end_id=self.end_id,
            start_exclusive=self.start_exclusive,
            end_inclusive=self.end_inclusive,
        )


@dataclass(frozen=True)
class Any:
    """Any is a message that can hold any other message as bytes. We don't use google.protobuf.Any because we want
    the JSON representation of the value field to be bytes."""

    type_url: str
    value: bytes

    @classmethod
    def from_message(cls, a: core_pb2.Any) -> "Any":
        return cls(type_url=a.type_url, value=a.value)

    def to_message(self) -> core_pb2.Any:
        return core_pb2.Any(type_url=self.type_url, value=self.value)


@dataclass(frozen=True)
class RepeatedAny:
    """RepeatedAny is a message holding a list of messages, that all share the same variable message type. It is
    preferrable over a simple list[Any] because it avoids repeating the type_url for every single element."""

    type_url: str
    value: list[bytes]

    @classmethod
    def from_message(cls, a: core_pb2.RepeatedAny) -> "RepeatedAny":
        return cls(type_url=a.type_url, value=list(a.value))

    def to_message(self) -> core_pb2.RepeatedAny:
        return core_pb2.RepeatedAny(type_url=self.type_url, value=self.value)


@dataclass(frozen=True)
class Datapoint:
    """Datapoint contains the metadata for a single data point."""

    meta: core_pb2.DatapointMetadata  # we keep this as protobuf message to easily convert to/from xarray
    data: Any

    @classmethod
    def from_message(
        cls, datapoint: core_pb2.Datapoint
    ) -> "Datapoint":  # lets use typing.Self once we require python >= 3.11
        """Convert a Datapoint protobuf message to a Datapoint object."""
        return cls(
            meta=datapoint.meta,
            data=Any.from_message(datapoint.data),
        )

    def to_message(self) -> core_pb2.Datapoint:
        return core_pb2.Datapoint(
            meta=self.meta,
            data=self.data.to_message(),
        )


@dataclass(frozen=True)
class Datapoints:
    meta: list[core_pb2.DatapointMetadata]  # we keep this as protobuf message to easily convert to/from xarray
    data: RepeatedAny

    @classmethod
    def from_message(cls, datapoints: core_pb2.Datapoints) -> "Datapoints":
        return cls(meta=list(datapoints.meta), data=RepeatedAny.from_message(datapoints.data))

    def to_message(self) -> core_pb2.Datapoints:
        return core_pb2.Datapoints(meta=self.meta, data=self.data.to_message())


@dataclass(frozen=True)
class DatapointPage:
    meta: list[core_pb2.DatapointMetadata]  # we keep this as protobuf message to easily convert to/from xarray
    data: RepeatedAny
    next_page: Pagination
    byte_size: int = field(compare=False)

    @classmethod
    def from_message(cls, datapoints: core_pb2.DatapointPage) -> "DatapointPage":
        return cls(
            meta=list(datapoints.meta),
            data=RepeatedAny.from_message(datapoints.data),
            next_page=Pagination.from_message(datapoints.next_page),
            byte_size=datapoints.ByteSize(),  # useful for progress bars
        )

    def to_message(self) -> core_pb2.DatapointPage:
        return core_pb2.DatapointPage(
            meta=self.meta,
            data=self.data.to_message(),
            next_page=self.next_page.to_message() if self.next_page else None,
        )


@dataclass(frozen=True)
class IngestDatapointsResponse:
    num_created: int
    num_existing: int
    datapoint_ids: list[UUID]

    @classmethod
    def from_message(cls, response: data_ingestion_pb2.IngestDatapointsResponse) -> "IngestDatapointsResponse":
        return cls(
            num_created=response.num_created,
            num_existing=response.num_existing,
            datapoint_ids=[uuid_message_to_uuid(datapoint_id) for datapoint_id in response.datapoint_ids],
        )

    def to_message(self) -> data_ingestion_pb2.IngestDatapointsResponse:
        return data_ingestion_pb2.IngestDatapointsResponse(
            num_created=self.num_created,
            num_existing=self.num_existing,
            datapoint_ids=[core_pb2.ID(uuid=datapoint_id.bytes) for datapoint_id in self.datapoint_ids],
        )


@dataclass(frozen=True)
class DeleteDatapointsResponse:
    num_deleted: int

    @classmethod
    def from_message(cls, response: data_ingestion_pb2.DeleteDatapointsResponse) -> "DeleteDatapointsResponse":
        return cls(
            num_deleted=response.num_deleted,
        )

    def to_message(self) -> data_ingestion_pb2.DeleteDatapointsResponse:
        return data_ingestion_pb2.DeleteDatapointsResponse(
            num_deleted=self.num_deleted,
        )
