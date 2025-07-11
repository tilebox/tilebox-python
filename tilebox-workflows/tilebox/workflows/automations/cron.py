from dataclasses import replace
from datetime import datetime, timezone
from typing import cast

try:
    from typing import Self
except ImportError:  # Self is only available in Python 3.11+
    from typing_extensions import Self


from tilebox.workflows.data import TriggeredCronEvent
from tilebox.workflows.task import RunnerContext, Task, deserialize_task, serialize_task
from tilebox.workflows.workflows.v1.automation_pb2 import Automation as AutomationMessage
from tilebox.workflows.workflows.v1.automation_pb2 import TriggeredCronEvent as TriggeredCronEventMessage

_NOT_TRIGGERED = TriggeredCronEvent(datetime.min.replace(tzinfo=timezone.utc))


class CronTask(Task):
    def __post_init__(self) -> None:
        self.trigger = _NOT_TRIGGERED

    def _serialize_args(self) -> bytes:
        return serialize_task(self)

    def _serialize(self) -> bytes:
        if self.trigger == _NOT_TRIGGERED:
            raise ValueError("CronTask cannot be submitted without being triggered. Use task.once().")
        event = self.trigger.to_message()
        args = self._serialize_args()
        message = AutomationMessage(
            trigger_event=event.SerializeToString(),
            args=args,
        )
        return message.SerializeToString()

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> Self:  # noqa: ARG003
        message = AutomationMessage()
        message.ParseFromString(task_input)

        task = cast(Self, deserialize_task(cls, message.args))

        event_message = TriggeredCronEventMessage()
        event_message.ParseFromString(message.trigger_event)
        event = TriggeredCronEvent.from_message(event_message)
        task.trigger = event
        return task

    def once(self, trigger_time: datetime | None = None) -> Self:
        trigger_time = datetime.now(tz=timezone.utc) if trigger_time is None else trigger_time.astimezone(timezone.utc)
        copy = replace(self)
        copy.trigger = TriggeredCronEvent(trigger_time)
        return copy
