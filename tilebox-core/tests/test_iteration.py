"""Verify shared pagination and bounded asynchronous consumption through their public helpers."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import pytest

from _tilebox.aio.concurrency import async_producer_consumer
from _tilebox.aio.pagination import paginated_request as async_paginated_request
from _tilebox.pagination import Pagination, paginated_request


@dataclass
class Page:
    limit: int | None = None
    starting_after: UUID | None = None


@dataclass
class Result:
    next_page: Page


@pytest.mark.asyncio
async def test_pagination_follows_cursor_until_exhausted() -> None:
    """Sync and async iteration request the next cursor once and stop after the final page."""
    initial = Page(limit=10)
    continuation = Page(limit=10, starting_after=UUID(int=1))
    first, last = Result(continuation), Result(Page())
    calls: list[Pagination] = []

    def request(page: Pagination) -> Result:
        calls.append(page)
        return first if page.starting_after is None else last

    assert list(paginated_request(request, initial)) == [first, last]
    assert calls == [initial, continuation]
    calls.clear()

    async def async_request(page: Pagination) -> Result:
        return request(page)

    assert [page async for page in async_paginated_request(async_request, initial)] == [first, last]
    assert calls == [initial, continuation]


@pytest.mark.asyncio
async def test_async_consumption_accepts_sync_and_async_callbacks() -> None:
    """Both callback forms receive every item in order, including None as a payload."""
    received: list[int | None] = []

    async def produce() -> AsyncIterator[int | None]:
        for value in (1, None, 2):
            yield value

    await async_producer_consumer(produce(), received.append, buffer_size=1)
    assert received == [1, None, 2]
    received.clear()

    async def consume(value: int | None) -> None:
        received.append(value)

    await async_producer_consumer(produce(), consume, buffer_size=1)
    assert received == [1, None, 2]
