from dataclasses import dataclass

from tilebox.datasets.datasetsv1 import core_pb2


@dataclass
class Pagination:
    limit: int | None = None
    starting_after: str | None = None

    @classmethod
    def from_message(cls, page: core_pb2.Pagination | None) -> "Pagination":
        if page is None:
            return cls()
        # convert falsish values (0 or empty string) to None
        return cls(limit=page.limit or None, starting_after=page.starting_after or None)

    def to_message(self) -> core_pb2.Pagination:
        return core_pb2.Pagination(limit=self.limit, starting_after=self.starting_after)
