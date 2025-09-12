import re

import pytest
from hypothesis import given
from tests.proto.test_pb2 import SampleArgs
from tests.tasks_data import storage_locations

from tilebox.workflows.automations import StorageEventTask
from tilebox.workflows.data import StorageEventType, StorageLocation
from tilebox.workflows.task import RunnerContext


class ExampleStorageEventTask(StorageEventTask):
    name: str
    value: int


class ExampleProtoStorageEventTask(StorageEventTask):
    args: SampleArgs


def test_storage_event_task_serialization() -> None:
    assert ExampleStorageEventTask("test", 42)._serialize_args() == b'{"name": "test", "value": 42}'


def test_storage_event_task_serialization_protobuf() -> None:
    assert (
        ExampleProtoStorageEventTask(SampleArgs(some_string="test", some_int=42))._serialize_args()
        == b"\n\x04test\x10*"
    )


def test_storage_event_task_serialization_requires_trigger() -> None:
    with pytest.raises(
        ValueError, match=re.escape("StorageEventTask cannot be submitted without being triggered. Use task.once().")
    ):
        ExampleStorageEventTask("test", 42)._serialize()


@given(storage_locations())
def test_storage_event_task_de_serialization_roundtrip(storage_location: StorageLocation) -> None:
    task = ExampleStorageEventTask("test", 42)
    triggered_task = task.once(storage_location, "FM171/apid.json", StorageEventType.CREATED)

    # serialized task only contains a bucket id, so for deserialization we need to provide a bucket lookup table
    context = RunnerContext(storage_locations=[storage_location])

    serialized = triggered_task._serialize()
    assert ExampleStorageEventTask._deserialize(serialized, context) == triggered_task


@given(storage_locations())
def test_storage_event_task_de_serialization_roundtrip_protobuf(storage_location: StorageLocation) -> None:
    task = ExampleProtoStorageEventTask(SampleArgs(some_string="test", some_int=42))
    triggered_task = task.once(storage_location, "FM171/apid.json")

    # serialized task only contains a bucket id, so for deserialization we need to provide a bucket lookup table
    context = RunnerContext(storage_locations=[storage_location])

    serialized = triggered_task._serialize()
    assert ExampleProtoStorageEventTask._deserialize(serialized, context) == triggered_task
