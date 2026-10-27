from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from protobuf import Message

from _tilebox.proto.tilebox.v1 import id_pb
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.query.time_interval import timestamp_to_datetime
from tilebox.datasets.uuid import uuid_message_to_uuid
from tilebox.datasets.v1 import core_pb, data_access_pb, data_ingestion_pb

DATAPOINT_METADATA_FIELDS = ("time", "id", "ingestion_time")


@dataclass(frozen=True)
class AnyMessage:
    """Any is a message that can hold any other message as bytes. We don't use google.protobuf.Any because we want
    the JSON representation of the value field to be bytes."""

    type_url: str
    value: bytes

    @classmethod
    def from_message(cls, a: core_pb.Any) -> "AnyMessage":
        return cls(type_url=a.type_url, value=a.value)

    def to_message(self) -> core_pb.Any:
        return core_pb.Any(type_url=self.type_url, value=self.value)


@dataclass(frozen=True)
class RepeatedAny:
    """RepeatedAny is a message holding a list of messages, that all share the same variable message type. It is
    preferrable over a simple list[Any] because it avoids repeating the type_url for every single element."""

    type_url: str
    value: list[bytes]

    @classmethod
    def from_message(cls, a: core_pb.RepeatedAny) -> "RepeatedAny":
        return cls(type_url=a.type_url, value=list(a.value))

    def to_message(self) -> core_pb.RepeatedAny:
        return core_pb.RepeatedAny(type_url=self.type_url, value=self.value)


@dataclass(frozen=True)
class QueryResultPage:
    data: RepeatedAny
    next_page: Pagination
    byte_size: int = field(compare=False)
    message_type: type[Message] | None = field(default=None, compare=False, repr=False)

    @classmethod
    def from_message(cls, page: data_access_pb.QueryResultPage) -> "QueryResultPage":
        return cls(
            data=RepeatedAny.from_message(page.data) if page.data is not None else RepeatedAny("", []),
            next_page=Pagination.from_message(page.next_page),
            byte_size=len(page.to_binary()),
        )

    def to_message(self) -> data_access_pb.QueryResultPage:
        return data_access_pb.QueryResultPage(
            data=self.data.to_message(),
            next_page=self.next_page.to_message(),
        )

    @property
    def n_datapoints(self) -> int:
        return len(self.data.value)

    @property
    def min_id(self) -> UUID:
        return uuid_message_to_uuid(self._parse_message(0).id)

    @property
    def max_id(self) -> UUID:
        return uuid_message_to_uuid(self._parse_message(-1).id)

    @property
    def min_time(self) -> datetime:
        return timestamp_to_datetime(self._parse_message(0).time)

    @property
    def max_time(self) -> datetime:
        return timestamp_to_datetime(self._parse_message(-1).time)

    def _parse_message(self, index: int) -> Any:
        if self.message_type is None:
            raise ValueError("Query page is not bound to a dataset schema")
        return self.message_type.from_binary(self.data.value[index])


@dataclass(frozen=True)
class IngestResponse:
    num_created: int
    num_existing: int
    datapoint_ids: list[UUID]

    @classmethod
    def from_message(cls, response: data_ingestion_pb.IngestResponse) -> "IngestResponse":
        return cls(
            num_created=response.num_created,
            num_existing=response.num_existing,
            datapoint_ids=[uuid_message_to_uuid(datapoint_id) for datapoint_id in response.datapoint_ids],
        )

    def to_message(self) -> data_ingestion_pb.IngestResponse:
        return data_ingestion_pb.IngestResponse(
            num_created=self.num_created,
            num_existing=self.num_existing,
            datapoint_ids=[id_pb.ID(uuid=datapoint_id.bytes) for datapoint_id in self.datapoint_ids],
        )
