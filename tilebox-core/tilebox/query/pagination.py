from dataclasses import dataclass
from uuid import UUID

from _tilebox.proto.tilebox.v1 import query_pb
from _tilebox.uuid import uuid_message_to_optional_uuid, uuid_to_uuid_message


@dataclass
class Pagination:
    limit: int | None = None
    starting_after: UUID | None = None

    @classmethod
    def from_message(cls, page: query_pb.Pagination | None) -> "Pagination":
        if page is None:
            return cls()
        # convert falsish values (0 or empty string) to None
        return cls(limit=page.limit or None, starting_after=uuid_message_to_optional_uuid(page.starting_after))

    def to_message(self) -> query_pb.Pagination:
        return query_pb.Pagination(limit=self.limit, starting_after=uuid_to_uuid_message(self.starting_after))
