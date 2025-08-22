import json
from dataclasses import dataclass
from typing import Annotated

import pytest

from tests.proto.test_pb2 import SampleArgs
from tilebox.workflows.data import TaskIdentifier
from tilebox.workflows.task import (
    ExecutionContext,
    Task,
    TaskMeta,
    _get_deserialization_field_type,
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


@dataclass(frozen=True, eq=True)
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


class ExampleTaskWithNestedJsonInList(Task):
    x: str
    nested_list: list[NestedJson]


def test_serialize_deserialize_task_nested_json_in_list() -> None:
    task = ExampleTaskWithNestedJsonInList("Hello", [NestedJson("World"), NestedJson("!")])
    assert deserialize_task(ExampleTaskWithNestedJsonInList, serialize_task(task)) == task


class ExampleTaskWithNestedJsonInTuple(Task):
    x: str
    nested_tuple: tuple[NestedJson, NestedJson]


def test_serialize_deserialize_task_nested_json_in_tuple() -> None:
    task = ExampleTaskWithNestedJsonInTuple("Hello", (NestedJson("World"), NestedJson("!")))
    assert deserialize_task(ExampleTaskWithNestedJsonInTuple, serialize_task(task)) == task


class ExampleTaskWithNestedJsonInVariadicTuple(Task):
    x: str
    nested_tuple: tuple[NestedJson, ...]


def test_serialize_deserialize_task_nested_json_in_variadic_tuple() -> None:
    task = ExampleTaskWithNestedJsonInVariadicTuple("Hello", (NestedJson("World"), NestedJson("!"), NestedJson("!!!")))
    assert deserialize_task(ExampleTaskWithNestedJsonInVariadicTuple, serialize_task(task)) == task


class ExampleTaskWithNestedJsonListOnly(Task):
    nested_list: list[NestedJson]


def test_serialize_deserialize_task_nested_json_list_only() -> None:
    task = ExampleTaskWithNestedJsonListOnly([NestedJson("World"), NestedJson("!")])
    assert deserialize_task(ExampleTaskWithNestedJsonListOnly, serialize_task(task)) == task


class ExampleTaskWithNestedJsonInDict(Task):
    x: str
    nested_list: dict[str, NestedJson]


def test_serialize_deserialize_task_nested_json_in_dict() -> None:
    task = ExampleTaskWithNestedJsonInDict("Hello", {"a": NestedJson("World"), "b": NestedJson("!")})
    assert deserialize_task(ExampleTaskWithNestedJsonInDict, serialize_task(task)) == task


class ExampleTaskWithNestedJsonInNestedDict(Task):
    x: str
    nested_list: dict[str, dict[str, list[NestedJson]]]


def test_serialize_deserialize_task_nested_json_in_nested_dict() -> None:
    task = ExampleTaskWithNestedJsonInNestedDict("Hello", {"a": {"b": [NestedJson("World"), NestedJson("!")]}})
    assert deserialize_task(ExampleTaskWithNestedJsonInNestedDict, serialize_task(task)) == task


class ExampleTaskWithNestedProtobufInList(Task):
    x: str
    nested_list: list[SampleArgs]


def test_serialize_deserialize_task_nested_protobuf_in_list() -> None:
    task = ExampleTaskWithNestedProtobufInList("Hello", [SampleArgs(some_string="World", some_int=123)])
    assert deserialize_task(ExampleTaskWithNestedProtobufInList, serialize_task(task)) == task


class ExampleTaskWithNestedProtobufInTuple(Task):
    x: str
    nested_tuple: tuple[SampleArgs, SampleArgs]


def test_serialize_deserialize_task_nested_protobuf_in_tuple() -> None:
    task = ExampleTaskWithNestedProtobufInTuple(
        "Hello", (SampleArgs(some_string="World", some_int=123), SampleArgs(some_string="!", some_int=456))
    )
    assert deserialize_task(ExampleTaskWithNestedProtobufInTuple, serialize_task(task)) == task


class ExampleTaskWithNestedProtobufInVariadicTuple(Task):
    x: str
    nested_tuple: tuple[SampleArgs, ...]


def test_serialize_deserialize_task_nested_protobuf_in_variadic_tuple() -> None:
    task = ExampleTaskWithNestedProtobufInVariadicTuple(
        "Hello",
        (
            SampleArgs(some_string="World", some_int=123),
            SampleArgs(some_string="!", some_int=456),
            SampleArgs(some_string="!!!", some_int=789),
        ),
    )
    assert deserialize_task(ExampleTaskWithNestedProtobufInVariadicTuple, serialize_task(task)) == task


class ExampleTaskWithNestedProtobufInDict(Task):
    x: str
    nested_dict: dict[str, SampleArgs]


def test_serialize_deserialize_task_nested_protobuf_in_dict() -> None:
    task = ExampleTaskWithNestedProtobufInDict(
        "Hello", {"a": SampleArgs(some_string="World", some_int=123), "b": SampleArgs(some_string="!", some_int=456)}
    )
    assert deserialize_task(ExampleTaskWithNestedProtobufInDict, serialize_task(task)) == task


class ExampleTaskWithNestedProtobufInNestedDict(Task):
    x: str
    nested_dict: dict[str, dict[str, list[SampleArgs]]]


def test_serialize_deserialize_task_nested_protobuf_in_nested_dict() -> None:
    task = ExampleTaskWithNestedProtobufInNestedDict(
        "Hello",
        {"a": {"b": [SampleArgs(some_string="World", some_int=123), SampleArgs(some_string="!", some_int=456)]}},
    )
    assert deserialize_task(ExampleTaskWithNestedProtobufInNestedDict, serialize_task(task)) == task


class ExampleTaskWithOptionalNestedJson(Task):
    x: str
    optional_args: NestedJson | None = None


def test_serialize_deserialize_task_nested_optional_json() -> None:
    task = ExampleTaskWithOptionalNestedJson("Hello")
    assert deserialize_task(ExampleTaskWithOptionalNestedJson, serialize_task(task)) == task

    task = ExampleTaskWithOptionalNestedJson("Hello", NestedJson(nested_x="World"))
    assert deserialize_task(ExampleTaskWithOptionalNestedJson, serialize_task(task)) == task


class ExampleTaskWithOptionalNestedProtobuf(Task):
    x: str
    optional_args: SampleArgs | None = None


def test_serialize_deserialize_task_nested_optional_protobuf() -> None:
    task = ExampleTaskWithOptionalNestedProtobuf("Hello")
    assert deserialize_task(ExampleTaskWithOptionalNestedProtobuf, serialize_task(task)) == task

    task = ExampleTaskWithOptionalNestedProtobuf("Hello", SampleArgs(some_string="World", some_int=123))
    assert deserialize_task(ExampleTaskWithOptionalNestedProtobuf, serialize_task(task)) == task


class FieldTypesTest(Task):
    field1: str
    field2: str | None
    field3: NestedJson | None
    field4: NestedJson | None
    field5: Annotated[NestedJson, "some description"]
    field6: Annotated[NestedJson, "some description"] | None
    field7: Annotated[NestedJson | None, "some description"]
    field8: Annotated[NestedJson | None, "some description"]
    field9: Annotated[list[NestedJson] | None, "some description"]


def test_get_deserialization_field_type() -> None:
    fields = FieldTypesTest.__dataclass_fields__
    assert _get_deserialization_field_type(fields["field1"].type) is str
    assert _get_deserialization_field_type(fields["field2"].type) is str
    assert _get_deserialization_field_type(fields["field3"].type) is NestedJson
    assert _get_deserialization_field_type(fields["field4"].type) is NestedJson
    assert _get_deserialization_field_type(fields["field5"].type) is NestedJson
    assert _get_deserialization_field_type(fields["field6"].type) is NestedJson
    assert _get_deserialization_field_type(fields["field7"].type) is NestedJson
    assert _get_deserialization_field_type(fields["field8"].type) is NestedJson
    assert _get_deserialization_field_type(fields["field9"].type) == list[NestedJson]
