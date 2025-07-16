from dataclasses import dataclass
from typing import TypeAlias
from uuid import UUID

from tilebox.datasets.tilebox.v1 import query_pb2
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message

IDIntervalLike: TypeAlias = "tuple[str, str] | tuple[UUID, UUID] | IDInterval"


@dataclass(frozen=True)
class IDInterval:
    start_id: UUID
    end_id: UUID
    start_exclusive: bool
    end_inclusive: bool

    @classmethod
    def from_message(cls, interval: query_pb2.IDInterval) -> "IDInterval":
        return cls(
            start_id=uuid_message_to_uuid(interval.start_id),
            end_id=uuid_message_to_uuid(interval.end_id),
            start_exclusive=interval.start_exclusive,
            end_inclusive=interval.end_inclusive,
        )

    def to_message(self) -> query_pb2.IDInterval:
        return query_pb2.IDInterval(
            start_id=uuid_to_uuid_message(self.start_id),
            end_id=uuid_to_uuid_message(self.end_id),
            start_exclusive=self.start_exclusive,
            end_inclusive=self.end_inclusive,
        )

    @classmethod
    def parse(cls, arg: IDIntervalLike, start_exclusive: bool = False, end_inclusive: bool = True) -> "IDInterval":
        """
        Convert a variety of input types to a IDInterval.

        Supported input types:
        - IDInterval: Return the input as is
        - tuple of two UUIDs: Return an IDInterval with start and end id set to the given values
        - tuple of two strings: Return an IDInterval with start and end id set to the UUIDs parsed from the given strings

        Args:
            arg: The input to convert
            start_exclusive: Whether the start id is exclusive
            end_inclusive: Whether the end id is inclusive

        Returns:
            IDInterval: The parsed ID interval
        """

        match arg:
            case IDInterval(_, _, _, _):
                return arg
            case (UUID(), UUID()):
                start, end = arg
                return IDInterval(
                    start_id=start,
                    end_id=end,
                    start_exclusive=start_exclusive,
                    end_inclusive=end_inclusive,
                )
            case (str(), str()):
                start, end = arg
                return IDInterval(
                    start_id=UUID(start),
                    end_id=UUID(end),
                    start_exclusive=start_exclusive,
                    end_inclusive=end_inclusive,
                )
