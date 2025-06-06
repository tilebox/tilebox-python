import time
from collections.abc import AsyncIterator, Iterator
from typing import cast

import anyio
import pytest

from _tilebox.grpc.aio.syncify import Syncifiable


class AsyncService(Syncifiable):
    async def async_method(self) -> int:
        return 42

    async def async_generator(self) -> AsyncIterator[int]:
        yield 42

    async def sleepy_async_generator(self, n: int = 5, sleep: float = 0.01) -> AsyncIterator[int]:
        for _ in range(n):
            await anyio.sleep(sleep)
            yield 42


def test_syncify() -> None:
    """Test that syncify works as expected."""
    service = AsyncService()
    service._syncify()
    assert cast(int, service.async_method()) == 42
    assert list(cast(Iterator[int], service.async_generator())) == [42]


@pytest.mark.asyncio()
async def test_syncify_in_running_event_loop() -> None:
    """Test that syncify works as expected when called from a running event loop."""
    service = AsyncService()
    service._syncify()
    assert cast(int, service.async_method()) == 42
    assert list(cast(Iterator[int], service.async_generator())) == [42]


@pytest.mark.asyncio()
async def test_syncify_generator_items_yielded_as_they_come_in() -> None:
    """
    Test that syncifing an async generator yields each item directly when it is available instead of a whole
    list of items at the end once the entire generator has completed.
    """
    service = AsyncService()
    service._syncify()

    sleep, eps = 0.01, 0.005

    before = time.time()
    for item in cast(Iterator[int], service.sleepy_async_generator(sleep=sleep)):
        delta = time.time() - before
        assert item == 42
        assert sleep - eps <= delta <= sleep + eps
        before = time.time()
