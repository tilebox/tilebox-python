import json
from dataclasses import dataclass
from typing import Annotated

import pytest

from tests.proto.test_pb2 import SampleArgs
from tilebox.workflows.cache import InMemoryCache
from tilebox.workflows.data import TaskIdentifier
from tilebox.workflows.runner.task_runner import ExecutionContext as RunnerExecutionContext
from tilebox.workflows.task import (
    ExecutionContext,
    Task,
    TaskMeta,
    _get_deserialization_field_type,
    deserialize_task,
    merge_future_tasks_to_submissions,
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

            def execute(self) -> None:  # ty: ignore[invalid-method-override]
                pass


def test_task_validation_execute_invalid_signature_too_many_params() -> None:
    with pytest.raises(TypeError, match="Expected a function signature of"):
        # validation happens at class creation time, that's why we create it in a function
        class TaskWithInvalidExecuteSignature(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                return "tilebox.tests.TaskWithInvalidExecuteSignature", "v0.1"

            def execute(self, context: ExecutionContext, invalid: int) -> None:  # ty: ignore[invalid-method-override]
                pass


def test_task_validation_execute_invalid_return_type() -> None:
    with pytest.raises(TypeError, match="to not have a return value"):
        # validation happens at class creation time, that's why we create it in a function
        class TaskWithInvalidExecuteReturnType(Task):
            @staticmethod
            def identifier() -> tuple[str, str]:
                return "tilebox.tests.TaskWithInvalidExecuteReturnType", "v0.1"

            def execute(self, context: ExecutionContext) -> int:  # ty: ignore[invalid-method-override]
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

    def _get_field_type(field_name: str) -> type:
        return _get_deserialization_field_type(fields[field_name].type)  # ty: ignore[invalid-argument-type]

    assert _get_field_type("field1") is str
    assert _get_field_type("field2") is str
    assert _get_field_type("field3") is NestedJson
    assert _get_field_type("field4") is NestedJson
    assert _get_field_type("field5") is NestedJson
    assert _get_field_type("field6") is NestedJson
    assert _get_field_type("field7") is NestedJson
    assert _get_field_type("field8") is NestedJson
    assert _get_field_type("field9") == list[NestedJson]


class TaskA(Task):
    x: int
    s: str

    def execute(self, context: ExecutionContext) -> None:
        pass


class TaskB(Task):
    f: float

    def execute(self, context: ExecutionContext) -> None:
        pass


def test_merge_future_tasks_to_submissions() -> None:
    context = RunnerExecutionContext(None, None, job_cache=InMemoryCache())  # ty: ignore[invalid-argument-type]
    tasks_1 = context.submit_subtasks([TaskA(3, "three"), TaskA(4, "four"), TaskA(5, "five")])
    tasks_2 = context.submit_subtasks([TaskB(3.2), TaskB(3.44), TaskB(3.55)], max_retries=1)
    tasks_3 = context.submit_subtasks([TaskA(6, "six"), TaskB(8.12)], cluster="other")

    submissions = merge_future_tasks_to_submissions(tasks_1 + tasks_2 + tasks_3, fallback_cluster="test")
    assert submissions is not None
    assert len(submissions.task_groups) == 1
    group = submissions.task_groups[0]
    assert group.dependencies_on_other_groups == []
    assert group.inputs == [
        serialize_task(TaskA(3, "three")),
        serialize_task(TaskA(4, "four")),
        serialize_task(TaskA(5, "five")),
        serialize_task(TaskB(3.2)),
        serialize_task(TaskB(3.44)),
        serialize_task(TaskB(3.55)),
        serialize_task(TaskA(6, "six")),
        serialize_task(TaskB(8.12)),
    ]
    assert group.cluster_slug_pointers == [0, 0, 0, 0, 0, 0, 1, 1]
    assert group.identifier_pointers == [0, 0, 0, 1, 1, 1, 0, 1]
    assert group.display_pointers == [0, 0, 0, 1, 1, 1, 0, 1]
    assert group.max_retries_values == [0, 0, 0, 1, 1, 1, 0, 0]

    assert submissions.cluster_slug_lookup == ["test", "other"]
    assert submissions.identifier_lookup == [TaskMeta.for_task(TaskA).identifier, TaskMeta.for_task(TaskB).identifier]
    assert submissions.display_lookup == ["TaskA", "TaskB"]


def test_merge_future_tasks_to_submissions_dependencies() -> None:
    context = RunnerExecutionContext(None, None, job_cache=InMemoryCache())  # ty: ignore[invalid-argument-type]
    tasks_1 = context.submit_subtasks([TaskA(2, "two"), TaskA(3, "three")])
    tasks_2 = context.submit_subtasks([TaskA(4, "four"), TaskA(5, "five")])
    tasks_3 = context.submit_subtasks([TaskB(3.2)], depends_on=tasks_1)
    tasks_4 = context.submit_subtasks([TaskB(3.44)])
    tasks_5 = context.submit_subtasks([TaskB(3.55)], depends_on=tasks_2)

    submissions = merge_future_tasks_to_submissions(
        tasks_1 + tasks_2 + tasks_3 + tasks_4 + tasks_5, fallback_cluster="test"
    )
    # tasks_1, tasks_2 and tasks_4 should not be merged, because they have different dependants
    # tasks_3 and tasks_5 should not be merged, because they have different dependencies

    assert submissions is not None
    assert len(submissions.task_groups) == 5
    assert submissions.task_groups[0].dependencies_on_other_groups == []
    assert submissions.task_groups[0].inputs == [serialize_task(TaskA(2, "two")), serialize_task(TaskA(3, "three"))]
    assert submissions.task_groups[1].dependencies_on_other_groups == []
    assert submissions.task_groups[1].inputs == [serialize_task(TaskA(4, "four")), serialize_task(TaskA(5, "five"))]
    assert submissions.task_groups[2].dependencies_on_other_groups == [0]
    assert submissions.task_groups[2].inputs == [serialize_task(TaskB(3.2))]
    assert submissions.task_groups[3].dependencies_on_other_groups == []
    assert submissions.task_groups[3].inputs == [serialize_task(TaskB(3.44))]
    assert submissions.task_groups[4].dependencies_on_other_groups == [1]
    assert submissions.task_groups[4].inputs == [serialize_task(TaskB(3.55))]


def test_merge_future_tasks_to_submissions_many_tasks() -> None:
    context = RunnerExecutionContext(None, None, job_cache=InMemoryCache())  # ty: ignore[invalid-argument-type]
    n = 100
    tasks_1 = context.submit_subtasks([TaskA(i, f"Task {i}") for i in range(n)])
    tasks_2 = context.submit_subtasks([TaskB(i / 3) for i in range(n)], depends_on=tasks_1)

    submissions = merge_future_tasks_to_submissions(tasks_1 + tasks_2, fallback_cluster="test")
    assert submissions is not None
    assert len(submissions.task_groups) == 2
    assert submissions.task_groups[0].dependencies_on_other_groups == []
    assert submissions.task_groups[0].identifier_pointers == [0] * n
    assert submissions.task_groups[1].dependencies_on_other_groups == [0]
    assert submissions.task_groups[1].identifier_pointers == [1] * n


def test_merge_future_tasks_to_submissions_many_non_mergeable_dependency_groups() -> None:
    context = RunnerExecutionContext(None, None, job_cache=InMemoryCache())  # ty: ignore[invalid-argument-type]
    n = 100
    for i in range(n):
        task_1 = context.submit_subtasks([TaskA(i, f"Task {i}")])
        context.submit_subtasks([TaskB(i / 3)], depends_on=task_1)

    submissions = merge_future_tasks_to_submissions(context._sub_tasks, fallback_cluster="test")
    assert submissions is not None
    assert len(submissions.task_groups) == 2 * n


def test_merge_future_tasks_two_separate_branches() -> None:
    context = RunnerExecutionContext(None, None, job_cache=InMemoryCache())  # ty: ignore[invalid-argument-type]
    task_a = context.submit_subtasks([TaskA(0, "Task 0")])
    # left branch
    task_b_left = context.submit_subtasks([TaskB(0.0)], depends_on=task_a)
    context.submit_subtasks([TaskB(1.0)], depends_on=task_b_left)

    # right branch
    task_b_right = context.submit_subtasks([TaskB(2.0)], depends_on=task_a)
    context.submit_subtasks([TaskB(3.0)], depends_on=task_b_right)

    submissions = merge_future_tasks_to_submissions(context._sub_tasks, fallback_cluster="test")
    assert submissions is not None
    assert len(submissions.task_groups) == 5
    assert submissions.task_groups[0].dependencies_on_other_groups == []
    assert submissions.task_groups[1].dependencies_on_other_groups == [0]
    assert submissions.task_groups[2].dependencies_on_other_groups == [1]
    assert submissions.task_groups[3].dependencies_on_other_groups == [0]
    assert submissions.task_groups[4].dependencies_on_other_groups == [3]
