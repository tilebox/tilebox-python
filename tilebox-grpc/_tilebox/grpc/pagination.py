from collections.abc import Callable, Iterator
from typing import Protocol, TypeVar
from uuid import UUID


class Pagination(Protocol):
    limit: int | None
    starting_after: UUID | None


class ResultPage(Protocol):
    @property
    def next_page(self) -> Pagination: ...


AnyResultPage = TypeVar("AnyResultPage", bound=ResultPage)


def paginated_request(
    paging_request: Callable[[Pagination], AnyResultPage],
    initial_page: Pagination,
) -> Iterator[AnyResultPage]:
    """Make a paginated request to a gRPC service endpoint.

    The endpoint is expected to return a next_page field, which is used for subsequent requests. Once no such
    next_page field is returned, the request is completed.

    Args:
        paging_request: A function that takes a page as input and returns a Datapoints object
            Often this will be a functools.partial object that wraps a gRPC service endpoint
            and only leaves the page argument remaining
        initial_page: The initial page to request

    Yields:
        Datapoints: The individual pages of the response
    """
    response = paging_request(initial_page)
    yield response

    while response.next_page.starting_after is not None:
        response = paging_request(response.next_page)
        yield response
