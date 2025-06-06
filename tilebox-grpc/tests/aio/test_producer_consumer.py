import time
from collections.abc import AsyncIterator, Callable

import anyio
import pytest

from _tilebox.grpc.aio.producer_consumer import async_producer_consumer


async def _mock_producer(n: int, sleep: float) -> AsyncIterator[int]:
    for i in range(n):
        await anyio.sleep(sleep)
        yield i


def _create_cpu_bound_consumer(processing_time: float, output_stack: list[int]) -> Callable[[int], None]:
    def _mock_consumer(item: int) -> None:
        time.sleep(processing_time)
        output_stack.append(item)

    return _mock_consumer


@pytest.mark.asyncio()
async def test_producer_consumer_slow_producer_fast_consumer() -> None:
    """
    Assert that the producer consumer pattern behaves as expected with a slow producer and a fast consumer.
    This means we make sure that each message is consumed as soon as it is produced, while we already wait for
    the next produced message.

    So the total time should be (producer_sleep * n + consumer_sleep) and not ((producer_sleep + consumer_sleep) * n)
    """
    n, producer_sleep, consumer_sleep = 10, 0.02, 0.01
    took = await _run_consumer_producer_example(n, producer_sleep, consumer_sleep)
    assert (producer_sleep * n + consumer_sleep) < took < ((producer_sleep + consumer_sleep) * n)


@pytest.mark.asyncio()
async def test_producer_consumer_equally_slow_producer_consumer() -> None:
    """
    Assert that the producer consumer pattern behaves as expected with a producer and a consumer that are equally slow.
    This means we make sure that each message is consumed as soon as it is produced, while we already wait for
    the next produced message.

    So the total time should be (producer_sleep * n + consumer_sleep) and not ((producer_sleep + consumer_sleep) * n)
    """
    n, producer_sleep, consumer_sleep = 10, 0.01, 0.01
    took = await _run_consumer_producer_example(n, producer_sleep, consumer_sleep)
    assert (producer_sleep * n + consumer_sleep) < took < ((producer_sleep + consumer_sleep) * n)


@pytest.mark.asyncio()
async def test_producer_consumer_fast_producer_slow_consumer() -> None:
    """
    Assert that the producer consumer pattern behaves as expected with a consumer that is slower than the producer.
    This means the messages are buffered in a message queue.

    So the total time should be (producer_sleep + consumer_sleep * n) and not ((producer_sleep + consumer_sleep) * n)
    """
    n, producer_sleep, consumer_sleep = 10, 0.01, 0.02
    took = await _run_consumer_producer_example(n, producer_sleep, consumer_sleep)
    assert (producer_sleep + consumer_sleep * n) < took < ((producer_sleep + consumer_sleep) * n)


async def _run_consumer_producer_example(n: int, producer_sleep: float, consumer_sleep: float) -> float:
    # helper function to simulate a producer consumer example
    outputs: list[int] = []
    producer = _mock_producer(n, producer_sleep)
    consumer = _create_cpu_bound_consumer(consumer_sleep, outputs)
    before = time.time()
    await async_producer_consumer(producer, consumer)
    assert outputs == list(range(n))
    return time.time() - before
