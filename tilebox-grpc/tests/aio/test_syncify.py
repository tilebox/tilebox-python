import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from typing import cast

import anyio
import pytest

from _tilebox.grpc.aio.syncify import Syncifiable, _run_blocking


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


@pytest.mark.asyncio
async def test_syncify_in_running_event_loop() -> None:
    """Test that syncify works as expected when called from a running event loop."""
    service = AsyncService()
    service._syncify()
    assert cast(int, service.async_method()) == 42
    assert list(cast(Iterator[int], service.async_generator())) == [42]


@pytest.mark.asyncio
async def test_syncify_preserves_current_task_in_nested_loop() -> None:
    outer_task = asyncio.current_task()
    loop = asyncio.get_running_loop()

    async def nested() -> int:
        inner_task = asyncio.current_task()
        assert inner_task is not None
        assert inner_task is not outer_task
        assert asyncio.get_running_loop() is loop
        assert inner_task in asyncio.all_tasks()
        await asyncio.sleep(0)
        assert asyncio.current_task() is inner_task
        return 73

    assert _run_blocking(nested()) == 73
    assert asyncio.current_task() is outer_task


@pytest.mark.asyncio
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
