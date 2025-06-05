from dataclasses import dataclass
from uuid import UUID

from tilebox.datasets.data.uuid import uuid_message_to_optional_uuid, uuid_to_uuid_message
from tilebox.datasets.datasetsv1 import core_pb2


@dataclass
class Pagination:
    limit: int | None = None
    starting_after: UUID | None = None

    @classmethod
    def from_message(cls, page: core_pb2.Pagination | None) -> "Pagination":
        if page is None:
            return cls()
        # convert falsish values (0 or empty string) to None
        return cls(limit=page.limit or None, starting_after=uuid_message_to_optional_uuid(page.starting_after))

    def to_message(self) -> core_pb2.Pagination:
        return core_pb2.Pagination(limit=self.limit, starting_after=uuid_to_uuid_message(self.starting_after))
