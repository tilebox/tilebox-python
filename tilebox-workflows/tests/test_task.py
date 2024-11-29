import json
from dataclasses import dataclass

import pytest

from tests.proto.test_pb2 import SampleArgs
from tilebox.workflows.data import TaskIdentifier
from tilebox.workflows.task import (
    ExecutionContext,
    Task,
    TaskMeta,
    deserialize_task,
    serialize_task,
)


def test_task_validation_simple_task() -> None:
    class SimpleTask(Task):
        pass

    expected_identifier = TaskIdentifier("SimpleTask", "v0.0")
    assert TaskMeta.for_task(SimpleTask).identifier == expected_identifier
    assert TaskMeta.for_task(SimpleTask).executable is False


def test_task_validation_simple_task_with_identifier() -> None:
    class SimpleTask(Task):
        @staticmethod
        def identifier() -> tuple[str, str]:
            return "tilebox.tests.SimpleTask", "v3.2"

    expected_identifier = TaskIdentifier("tilebox.tests.SimpleTask", "v3.2")
    assert TaskMeta.for_task(SimpleTask).identifier == expected_identifier


def test_task_validation_simple_task_executable() -> None:
    class SimpleTask(Task):
        def execute(self, context: ExecutionContext) -> None:
            pass

    assert TaskMeta.for_task(SimpleTask).executable is True


def test_task_validation_execute_invalid_signature_no_params() -> None:
    with pytest.raises(TypeError, match="Expected a function signature of"):
        # validation happens at class creation time, that's why we create it in a function
        class TaskWithInvalidExecuteSignature(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                return "tilebox.tests.TaskWithInvalidExecuteSignature", "v0.1"

            def execute(self) -> None:  # type: ignore[override]
                pass


def test_task_validation_execute_invalid_signature_too_many_params() -> None:
    with pytest.raises(TypeError, match="Expected a function signature of"):
        # validation happens at class creation time, that's why we create it in a function
        class TaskWithInvalidExecuteSignature(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                return "tilebox.tests.TaskWithInvalidExecuteSignature", "v0.1"

            def execute(self, context: ExecutionContext, invalid: int) -> None:  # type: ignore[override]
                pass


def test_task_validation_execute_invalid_return_type() -> None:
    with pytest.raises(TypeError, match="to not have a return value"):
        # validation happens at class creation time, that's why we create it in a function
        class TaskWithInvalidExecuteReturnType(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                return "tilebox.tests.TaskWithInvalidExecuteReturnType", "v0.1"

            def execute(self, context: ExecutionContext) -> int:  # type: ignore[override]
                _ = context
                return 5


def test_task_validation_used_defined_identifier_classmethod() -> None:
    class SimpleTaskWithClassmethodIdentifier(Task):
        @classmethod
        def identifier(cls) -> tuple[str, str]:
            return "tilebox.tests.SimpleTaskWithClassmethodIdentifier", "v3.2"

    expected_identifier = TaskIdentifier("tilebox.tests.SimpleTaskWithClassmethodIdentifier", "v3.2")
    assert TaskMeta.for_task(SimpleTaskWithClassmethodIdentifier).identifier == expected_identifier


def test_task_user_defined_identifier_invalid_signature() -> None:
    with pytest.raises(TypeError, match="Failed to invoke"):

        class TaskIdentifierNotStaticMethod(Task):
            def identifier(self) -> tuple[str, str]:
                return "tilebox.tests.TaskIdentifierNotStaticMethod", "v0.1"

            def execute(self, context: ExecutionContext) -> None:
                pass


def test_task_user_defined_identifier_no_name() -> None:
    with pytest.raises(TypeError, match="A task name is required"):

        class TaskIdentifierNoName(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                return "", "v0.1"

            def execute(self, context: ExecutionContext) -> None:
                pass


def test_task_user_defined_identifier_name_too_long() -> None:
    with pytest.raises(TypeError, match="The task name is too long"):

        class TaskIdentifierNameTooLong(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                name = "a" * (256 + 1)
                return name, "v0.1"

            def execute(self, context: ExecutionContext) -> None:
                pass


@pytest.mark.parametrize("version", ["", "3.2", "v3.2.1", "v3", "v3.", "something-else"])
def test_task_user_defined_identifier_invalid_version(version: str) -> None:
    with pytest.raises(TypeError, match="Invalid version"):

        class TaskIdentifierInvalidVersion(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                return "tilebox.tests.TaskIdentifierInvalidVersion", version


class ExampleTask(Task):
    @staticmethod
    def identifier() -> tuple[str, str]:
        return "test_task.ExampleTask", "v0.1"


class ExampleTaskNoArgs(Task):
    pass


def test_serialize_no_args() -> None:
    task = ExampleTaskNoArgs()
    assert serialize_task(task) == b""


def test_deserialize_no_args() -> None:
    assert deserialize_task(ExampleTaskNoArgs, b"") == ExampleTaskNoArgs()


class ExampleTaskWithArg(Task):
    x: str


def test_serialize_one_arg_json() -> None:
    task = ExampleTaskWithArg("Hello")
    assert serialize_task(task) == json.dumps("Hello").encode()


def test_serialize_deserialize_one_arg_json() -> None:
    task = ExampleTaskWithArg("Hello")
    assert deserialize_task(ExampleTaskWithArg, serialize_task(task)) == task


class ExampleTaskWithMultipleArgs(Task):
    x: str
    y: int


def test_serialize_multiple_args_json() -> None:
    task = ExampleTaskWithMultipleArgs("Hello", 123)
    assert serialize_task(task) == json.dumps({"x": "Hello", "y": 123}).encode()


def test_serialize_deserialize_multiple_args_json() -> None:
    task = ExampleTaskWithMultipleArgs("Hello", 123)
    assert deserialize_task(ExampleTaskWithMultipleArgs, serialize_task(task)) == task


class ExampleProtobufTaskWithSingleProtobufArg(Task):
    arg: SampleArgs


def test_serialize_protobuf() -> None:
    task = ExampleProtobufTaskWithSingleProtobufArg(SampleArgs(some_string="Hello", some_int=123))
    assert serialize_task(task) == b"\n\x05Hello\x10{"


def test_serialize_deserialize_task_protobuf() -> None:
    task = ExampleProtobufTaskWithSingleProtobufArg(SampleArgs(some_string="Hello", some_int=123))
    assert deserialize_task(ExampleProtobufTaskWithSingleProtobufArg, serialize_task(task)) == task


@dataclass
class NestedJson:
    nested_x: str


@dataclass
class DoublyNestedJson:
    doubly_nested_x: str
    nested: NestedJson


class ExampleTaskWithNestedJson(Task):
    x: str
    nested: DoublyNestedJson


def test_serialize_deserialize_task_nested_json() -> None:
    task = ExampleTaskWithNestedJson("Hello", DoublyNestedJson("World", NestedJson("!")))
    assert deserialize_task(ExampleTaskWithNestedJson, serialize_task(task)) == task


class ExampleTaskWithNestedProtobuf(Task):
    x: str
    nested: SampleArgs


def test_serialize_deserialize_task_nested_protobuf() -> None:
    task = ExampleTaskWithNestedProtobuf("Hello", SampleArgs(some_string="World", some_int=123))
    assert deserialize_task(ExampleTaskWithNestedProtobuf, serialize_task(task)) == task
