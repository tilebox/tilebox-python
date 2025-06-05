from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

from tilebox.datasets.data.pagination import Pagination
from tilebox.datasets.data.time_interval import timestamp_to_datetime
from tilebox.datasets.data.uuid import uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.datasets.datasetsv1 import core_pb2, data_access_pb2, data_ingestion_pb2
from tilebox.datasets.message_pool import get_message_type

DatapointIntervalLike: TypeAlias = "tuple[str, str] | tuple[UUID, UUID] | DatapointInterval"


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

    @classmethod
    def parse(
        cls, arg: DatapointIntervalLike, start_exclusive: bool = False, end_inclusive: bool = True
    ) -> "DatapointInterval":
        """
        Convert a variety of input types to a DatapointInterval.

        Supported input types:
        - DatapointInterval: Return the input as is
        - tuple of two UUIDs: Return an DatapointInterval with start and end id set to the given values
        - tuple of two strings: Return an DatapointInterval with start and end id set to the UUIDs parsed from the given strings

        Args:
            arg: The input to convert
            start_exclusive: Whether the start id is exclusive
            end_inclusive: Whether the end id is inclusive

        Returns:
            DatapointInterval: The parsed ID interval
        """

        match arg:
            case DatapointInterval(_, _, _, _):
                return arg
            case (UUID(), UUID()):
                start, end = arg
                return DatapointInterval(
                    start_id=start,
                    end_id=end,
                    start_exclusive=start_exclusive,
                    end_inclusive=end_inclusive,
                )
            case (str(), str()):
                start, end = arg
                return DatapointInterval(
                    start_id=UUID(start),
                    end_id=UUID(end),
                    start_exclusive=start_exclusive,
                    end_inclusive=end_inclusive,
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
