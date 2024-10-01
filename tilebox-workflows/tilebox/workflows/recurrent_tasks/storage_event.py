from dataclasses import replace
from typing import TypeVar, cast
from uuid import UUID

from tilebox.workflows.data import (
    StorageEventType,
    StorageLocation,
    StorageType,
    TriggeredStorageEvent,
)
from tilebox.workflows.task import AsyncTask, RunnerContext, SyncTask, deserialize_task, serialize_task
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTask as RecurrentTaskMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import TriggeredStorageEvent as TriggeredStorageEventMessage

_NOT_TRIGGERED = TriggeredStorageEvent(
    StorageLocation(UUID(int=0), "", StorageType.FS),
    StorageEventType.CREATED,
    "",
)


class SyncStorageEventTask(SyncTask):
    def __post_init__(self) -> None:
        self.trigger = _NOT_TRIGGERED

    def _serialize_args(self) -> bytes:
        return serialize_task(self)

    def _serialize(self) -> bytes:
        return _serialize_storage_event_task(self)

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> "SyncStorageEventTask":
        return _deserialize_storage_event_task(cls, task_input, context)

    def once(
        self,
        storage_location: StorageLocation,
        object: str,  # noqa: A002
        type: StorageEventType = StorageEventType.CREATED,  # noqa: A002
    ) -> "SyncStorageEventTask":
        return _trigger_once(self, storage_location, object, type)


class AsyncStorageEventTask(AsyncTask):
    def __post_init__(self) -> None:
        self.trigger = _NOT_TRIGGERED

    def _serialize_args(self) -> bytes:
        return serialize_task(self)

    def _serialize(self) -> bytes:
        return _serialize_storage_event_task(self)

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> "AsyncStorageEventTask":
        return _deserialize_storage_event_task(cls, task_input, context)

    def once(
        self,
        storage_location: StorageLocation,
        object: str,  # noqa: A002
        type: StorageEventType = StorageEventType.CREATED,  # noqa: A002
    ) -> "AsyncStorageEventTask":
        return _trigger_once(self, storage_location, object, type)


T = TypeVar("T", SyncStorageEventTask, AsyncStorageEventTask)


def _serialize_storage_event_task(storage_event_task: T) -> bytes:
    if storage_event_task.trigger == _NOT_TRIGGERED:
        raise ValueError("StorageEventTask cannot be submitted without being triggered. Use task.once().")
    event = storage_event_task.trigger.to_message()
    args = storage_event_task._serialize_args()  # noqa: SLF001
    message = RecurrentTaskMessage(
        trigger_event=event.SerializeToString(),
        args=args,
    )
    return message.SerializeToString()


def _deserialize_storage_event_task(
    storage_event_task_class: type, task_input: bytes, context: RunnerContext | None = None
) -> T:
    message = RecurrentTaskMessage()
    message.ParseFromString(task_input)

    task = cast(T, deserialize_task(storage_event_task_class, message.args))

    event_message = TriggeredStorageEventMessage()
    event_message.ParseFromString(message.trigger_event)
    if context is None:
        raise ValueError("No storage locations available in runner context, cannot deserialize storage event task.")
    event = TriggeredStorageEvent.from_message(event_message, context.storage_locations)
    task.trigger = event
    return task


def _trigger_once(storage_event_task: T, sl: StorageLocation, object: str, type: StorageEventType) -> T:  # noqa: A002
    copy = replace(storage_event_task)
    copy.trigger = TriggeredStorageEvent(sl, type, object)
    return copy
