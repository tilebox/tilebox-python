from datetime import datetime, timezone

import betterproto
import pytest

from tilebox.workflows.recurrent_tasks import CronTask


class ExampleCronTask(CronTask):
    name: str
    value: int


class ExampleProtoCronTask(CronTask, betterproto.Message):
    name: str = betterproto.string_field(1)
    value: int = betterproto.int64_field(2)


def test_cron_task_serialization() -> None:
    assert ExampleCronTask("test", 42)._serialize_args() == b'{"name": "test", "value": 42}'


def test_cron_task_serialization_protobuf() -> None:
    assert ExampleProtoCronTask("test", 42)._serialize_args() == b"\n\x04test\x10*"


def test_cron_task_serialization_requires_trigger() -> None:
    with pytest.raises(ValueError, match="CronTask cannot be submitted without being triggered. Use task.once()."):
        ExampleCronTask("test", 42)._serialize()


def test_cron_task_de_serialization_roundtrip() -> None:
    task = ExampleCronTask("test", 42)
    triggered_task = task.once(trigger_time=datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc))

    serialized = triggered_task._serialize()
    assert serialized == b'\n\x08\n\x06\x08\x80\xcc\xb9\xff\x05\x12\x1d{"name": "test", "value": 42}'
    assert ExampleCronTask._deserialize(serialized) == triggered_task


def test_cron_task_de_serialization_roundtrip_protobuf() -> None:
    task = ExampleProtoCronTask("test", 42)
    triggered_task = task.once(trigger_time=datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc))

    serialized = triggered_task._serialize()
    assert serialized == b"\n\x08\n\x06\x08\x80\xcc\xb9\xff\x05\x12\x08\n\x04test\x10*"
    assert ExampleProtoCronTask._deserialize(serialized) == triggered_task
