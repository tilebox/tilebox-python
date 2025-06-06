import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeVar

from anyio import EndOfStream, create_memory_object_stream, create_task_group
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

T = TypeVar("T")


async def async_producer_consumer(
    producer: AsyncIterator[T],
    consumer: Callable[[T], None] | Callable[[T], Awaitable[Any]],
    buffer_size: int = 10,
) -> None:
    """
    Consume messages from a async producer (e.g. a service endpoint) as they come on. This ensures that the consumer
    is already computing each produced message while the next message is being produced.

    If the consumer is actually slower than the producer producing new message, the messages are buffered up to the
    given buffer size. If the buffer is full, the producer will block until the consumer has consumed a message.

    Args:
        producer: The async generator to consume from
        consumer: The consumer function to call for each message
        buffer_size: The maximum number of messages to buffer before blocking the producer
    """
    streams: Any = create_memory_object_stream(max_buffer_size=buffer_size)
    send: MemoryObjectSendStream[T] = streams[0]
    receive: MemoryObjectReceiveStream[T] = streams[1]
    async with create_task_group() as task_group:
        task_group.start_soon(_producer, producer, send)
        task_group.start_soon(_consumer, consumer, receive)


async def _producer(producer: AsyncIterator[T], send_stream: MemoryObjectSendStream[T]) -> None:
    """
    Forward all messages from a producer (async iterator) and send them to a buffered send stream.
    """
    async for message in producer:
        await send_stream.send(message)
    send_stream.close()


async def _consumer(
    consume: Callable[[T], None] | Callable[[T], Awaitable[Any]], receive_stream: MemoryObjectReceiveStream[T]
) -> None:
    """
    Receive messages from a buffered receive stream and forward them to a consumer until no more messages are available.
    """
    try:
        while True:
            message = await receive_stream.receive()
            result = consume(message)
            if inspect.iscoroutine(result):
                await result
    except EndOfStream:
        pass
    receive_stream.close()
