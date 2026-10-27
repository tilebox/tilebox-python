from dataclasses import replace
from typing import Self
from uuid import UUID

from tilebox.workflows.data import (
    StorageEventType,
    StorageLocation,
    StorageType,
    TriggeredStorageEvent,
)
from tilebox.workflows.task import RunnerContext, Task, deserialize_task, serialize_task
from tilebox.workflows.v1.automation_pb import Automation as AutomationMessage
from tilebox.workflows.v1.storage_location_pb import TriggeredStorageEvent as TriggeredStorageEventMessage

_NOT_TRIGGERED = TriggeredStorageEvent(
    StorageLocation(UUID(int=0), "", StorageType.LOCAL),
    StorageEventType.CREATED,
    "",
)


class StorageEventTask(Task):
    def __post_init__(self) -> None:
        self.trigger = _NOT_TRIGGERED

    def _serialize_args(self) -> bytes:
        return serialize_task(self)

    def _serialize(self) -> bytes:
        if self.trigger == _NOT_TRIGGERED:
            raise ValueError("StorageEventTask cannot be submitted without being triggered. Use task.once().")
        event = self.trigger.to_message()
        args = self._serialize_args()
        message = AutomationMessage(
            trigger_event=event.to_binary(),
            args=args,
        )
        return message.to_binary()

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> Self:
        message = AutomationMessage.from_binary(task_input)

        task = deserialize_task(cls, message.args)

        event_message = TriggeredStorageEventMessage.from_binary(message.trigger_event)
        if context is None:
            raise ValueError("No storage locations available in runner context, cannot deserialize storage event task.")
        event = TriggeredStorageEvent.from_message(event_message, context.storage_locations)
        task.trigger = event
        return task

    def once(
        self,
        storage_location: StorageLocation,
        object_location: str,
        event_type: StorageEventType = StorageEventType.CREATED,
    ) -> Self:
        copy = replace(self)
        copy.trigger = TriggeredStorageEvent(storage_location, event_type, object_location)
        return copy
