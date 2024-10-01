from dataclasses import replace
from datetime import datetime, timezone
from typing import TypeVar, cast

from tilebox.workflows.data import TriggeredCronEvent
from tilebox.workflows.task import AsyncTask, RunnerContext, SyncTask, deserialize_task, serialize_task
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTask as RecurrentTaskMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import TriggeredCronEvent as TriggeredCronEventMessage

_NOT_TRIGGERED = TriggeredCronEvent(datetime.min.replace(tzinfo=timezone.utc))


class SyncCronTask(SyncTask):
    def __post_init__(self) -> None:
        self.trigger = _NOT_TRIGGERED

    def _serialize_args(self) -> bytes:
        return serialize_task(self)

    def _serialize(self) -> bytes:
        return _serialize_cron_task(self)

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> "SyncCronTask":
        return _deserialize_cron_task(cls, task_input, context)

    def once(self, trigger_time: datetime | None = None) -> "SyncCronTask":
        return _trigger_once(self, trigger_time)


class AsyncCronTask(AsyncTask):
    def __post_init__(self) -> None:
        self.trigger = _NOT_TRIGGERED

    def _serialize_args(self) -> bytes:
        return serialize_task(self)

    def _serialize(self) -> bytes:
        return _serialize_cron_task(self)

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> "AsyncCronTask":
        return _deserialize_cron_task(cls, task_input, context)

    def once(self, trigger_time: datetime | None = None) -> "AsyncCronTask":
        return _trigger_once(self, trigger_time)


T = TypeVar("T", SyncCronTask, AsyncCronTask)


def _serialize_cron_task(cron_task: T) -> bytes:
    if cron_task.trigger == _NOT_TRIGGERED:
        raise ValueError("CronTask cannot be submitted without being triggered. Use task.once().")
    event = cron_task.trigger.to_message()
    args = cron_task._serialize_args()  # noqa: SLF001
    message = RecurrentTaskMessage(
        trigger_event=event.SerializeToString(),
        args=args,
    )
    return message.SerializeToString()


def _deserialize_cron_task(cron_task_class: type, task_input: bytes, context: RunnerContext | None = None) -> T:  # noqa: ARG001
    message = RecurrentTaskMessage()
    message.ParseFromString(task_input)

    task = cast(T, deserialize_task(cron_task_class, message.args))

    event_message = TriggeredCronEventMessage()
    event_message.ParseFromString(message.trigger_event)
    event = TriggeredCronEvent.from_message(event_message)
    task.trigger = event
    return task


def _trigger_once(cron_task: T, trigger_time: datetime | None = None) -> T:
    trigger_time = datetime.now(tz=timezone.utc) if trigger_time is None else trigger_time.astimezone(timezone.utc)
    copy = replace(cron_task)
    copy.trigger = TriggeredCronEvent(trigger_time)
    return copy
