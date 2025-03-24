from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from tilebox.datasets.data.pagination import Pagination
from tilebox.datasets.data.time_interval import timestamp_to_datetime
from tilebox.datasets.data.uuid import uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.datasets.datasetsv1 import core_pb2, data_access_pb2, data_ingestion_pb2
from tilebox.datasets.message_pool import get_message_type


@dataclass(frozen=True)
class DatapointInterval:
    start_id: UUID
    end_id: UUID
    start_exclusive: bool
    end_inclusive: bool

    @classmethod
    def from_message(cls, interval: core_pb2.DatapointInterval) -> "DatapointInterval":
        return cls(
            start_id=uuid_message_to_uuid(interval.start_id),
            end_id=uuid_message_to_uuid(interval.end_id),
            start_exclusive=interval.start_exclusive,
            end_inclusive=interval.end_inclusive,
        )

    def to_message(self) -> core_pb2.DatapointInterval:
        return core_pb2.DatapointInterval(
            start_id=uuid_to_uuid_message(self.start_id),
            end_id=uuid_to_uuid_message(self.end_id),
            start_exclusive=self.start_exclusive,
            end_inclusive=self.end_inclusive,
        )


@dataclass(frozen=True)
class AnyMessage:
    """Any is a message that can hold any other message as bytes. We don't use google.protobuf.Any because we want
    the JSON representation of the value field to be bytes."""

    type_url: str
    value: bytes

    @classmethod
    def from_message(cls, a: core_pb2.Any) -> "AnyMessage":
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
    data: AnyMessage

    @classmethod
    def from_message(
        cls, datapoint: core_pb2.Datapoint
    ) -> "Datapoint":  # lets use typing.Self once we require python >= 3.11
        """Convert a Datapoint protobuf message to a Datapoint object."""
        return cls(
            meta=datapoint.meta,
            data=AnyMessage.from_message(datapoint.data),
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
            next_page=Pagination.from_legacy_message(datapoints.next_page),
            byte_size=datapoints.ByteSize(),  # useful for progress bars
        )

    def to_message(self) -> core_pb2.DatapointPage:
        return core_pb2.DatapointPage(
            meta=self.meta,
            data=self.data.to_message(),
            next_page=self.next_page.to_legacy_message() if self.next_page else None,
        )

    @property
    def n_datapoints(self) -> int:
        return len(self.data.value)

    def min_id(self) -> UUID:
        return UUID(self.meta[0].id)

    def max_id(self) -> UUID:
        return UUID(self.meta[-1].id)

    def min_time(self) -> datetime:
        return timestamp_to_datetime(self.meta[0].event_time)

    def max_time(self) -> datetime:
        return timestamp_to_datetime(self.meta[-1].event_time)


@dataclass(frozen=True)
class QueryResultPage:
    data: RepeatedAny
    next_page: Pagination
    byte_size: int = field(compare=False)

    @classmethod
    def from_message(cls, page: data_access_pb2.QueryResultPage) -> "QueryResultPage":
        return cls(
            data=RepeatedAny.from_message(page.data),
            next_page=Pagination.from_message(page.next_page),
            byte_size=page.ByteSize(),
        )

    def to_message(self) -> data_access_pb2.QueryResultPage:
        return data_access_pb2.QueryResultPage(
            data=self.data.to_message(),
            next_page=self.next_page.to_message(),
        )

    @property
    def n_datapoints(self) -> int:
        return len(self.data.value)

    def min_id(self) -> UUID:
        return uuid_message_to_uuid(self._parse_message(0).id)

    def max_id(self) -> UUID:
        return uuid_message_to_uuid(self._parse_message(-1).id)

    def min_time(self) -> datetime:
        return timestamp_to_datetime(self._parse_message(0).time)

    def max_time(self) -> datetime:
        return timestamp_to_datetime(self._parse_message(-1).time)

    def _parse_message(self, index: int) -> Any:
        message_type = get_message_type(self.data.type_url)
        return message_type.FromString(self.data.value[index])


@dataclass(frozen=True)
class IngestResponse:
    num_created: int
    num_existing: int
    datapoint_ids: list[UUID]

    @classmethod
    def from_message(cls, response: data_ingestion_pb2.IngestResponse) -> "IngestResponse":
        return cls(
            num_created=response.num_created,
            num_existing=response.num_existing,
            datapoint_ids=[uuid_message_to_uuid(datapoint_id) for datapoint_id in response.datapoint_ids],
        )

    def to_message(self) -> data_ingestion_pb2.IngestResponse:
        return data_ingestion_pb2.IngestResponse(
            num_created=self.num_created,
            num_existing=self.num_existing,
            datapoint_ids=[core_pb2.ID(uuid=datapoint_id.bytes) for datapoint_id in self.datapoint_ids],
        )
