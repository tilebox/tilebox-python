from collections.abc import Callable, Iterator
from queue import Queue
from threading import Thread
from typing import Any, TypeVar

T = TypeVar("T")


def concurrent_producer_consumer(
    producer: Iterator[T],
    consumer: Callable[[T], None] | Callable[[T], Any],
    buffer_size: int = 10,
) -> None:
    """
    Consume messages from a producer (e.g. a service endpoint) as they come in. This ensures that the consumer
    is already computing each produced message while the next message is being produced.

    If the consumer is actually slower than the producer producing new message, the messages are buffered up to the
    given buffer size. If the buffer is full, the producer will block until the consumer has consumed a message.

    Args:
        producer: The generator to consume from
        consumer: The consumer function to call for each message
        buffer_size: The maximum number of messages to buffer before blocking the producer
    """

    queue = Queue(maxsize=buffer_size)

    # offload consuming to a separate thread, so that we can continue producing data on the main thread
    consumer_thread = Thread(target=_consumer, args=(consumer, queue))
    consumer_thread.start()
    # do this on the main thread - the producer may have callbacks (e.g. progress bar updates) and those should
    # happen on the main thread - otherwise issues may arise with libraries like streamlit
    _producer(producer, queue)
    consumer_thread.join()


def _producer(producer: Iterator[T], queue: Queue[T | None]) -> None:
    """
    Forward all messages from a producer (async iterator) and send them to a buffered send stream.
    """
    for message in producer:
        queue.put(message, block=True)

    queue.put(None, block=True)  # indicate that we are done


def _consumer(consume: Callable[[T], None] | Callable[[T], Any], queue: Queue[T | None]) -> None:
    """
    Receive messages from a buffered receive stream and forward them to a consumer until no more messages are available.
    """
    while True:
        message = queue.get(block=True)
        if message is None:
            break
        consume(message)
