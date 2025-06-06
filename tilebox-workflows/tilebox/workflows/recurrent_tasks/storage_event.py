from dataclasses import replace
from typing import cast
from uuid import UUID

try:
    from typing import Self
except ImportError:  # Self is only available in Python 3.11+
    from typing_extensions import Self

from tilebox.workflows.data import (
    StorageEventType,
    StorageLocation,
    StorageType,
    TriggeredStorageEvent,
)
from tilebox.workflows.task import RunnerContext, Task, deserialize_task, serialize_task
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTask as RecurrentTaskMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import TriggeredStorageEvent as TriggeredStorageEventMessage

_NOT_TRIGGERED = TriggeredStorageEvent(
    StorageLocation(UUID(int=0), "", StorageType.FS),
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
        message = RecurrentTaskMessage(
            trigger_event=event.SerializeToString(),
            args=args,
        )
        return message.SerializeToString()

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> Self:
        message = RecurrentTaskMessage()
        message.ParseFromString(task_input)

        task = cast(cls, deserialize_task(cls, message.args))

        event_message = TriggeredStorageEventMessage()
        event_message.ParseFromString(message.trigger_event)
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
