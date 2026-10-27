"""Bounded producer/consumer concurrency with exception propagation."""

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Full, Queue
from threading import Event
from typing import TypeVar

T = TypeVar("T")


def concurrent_producer_consumer(
    producer: Iterator[T],
    consumer: Callable[[T], object],
    buffer_size: int = 10,
) -> None:
    """Produce on the calling thread and consume on one worker, propagating failures."""
    if buffer_size < 1:
        raise ValueError("buffer_size must be positive")
    queue: Queue[T] = Queue(buffer_size)
    done = Event()

    def consume() -> None:
        while not done.is_set() or not queue.empty():
            try:
                item = queue.get(timeout=0.05)
            except Empty:
                continue
            consumer(item)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(consume)
        try:
            for item in producer:
                while True:
                    if future.done():
                        future.result()
                    try:
                        queue.put(item, timeout=0.05)
                        break
                    except Full:
                        continue
        finally:
            done.set()
        future.result()
