import inspect
import typing
from abc import ABC, ABCMeta, abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Sequence
from contextlib import suppress
from dataclasses import dataclass, fields, is_dataclass
from types import NoneType, UnionType
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast, get_args, get_origin

# from python 3.11 onwards this is available as typing.dataclass_transform:
from typing_extensions import dataclass_transform

from tilebox.workflows._serialization import decode_json, encode_json_field, encode_json_fields
from tilebox.workflows.data import RunnerContext, TaskIdentifier, TaskSubmissionGroup, TaskSubmissions

if TYPE_CHECKING:
    from tilebox.workflows.observability.logging import StructuredLogger
    from tilebox.workflows.observability.tracing import WorkflowTracer
else:
    StructuredLogger = Any
    WorkflowTracer = Any

META_ATTR = "__tilebox_task_meta__"  # the name of the attribute we use to store task metadata on the class


class _Taskify(type):
    """A metaclass for tasks performing some validation on user-defined task classes.

    Metaclasses are a bit of a dark art in Python. They are used to customize the creation of a class. In this case,
    the metaclass is responsible for validating that a task class has a valid execute method and for generating a
    unique identifier for the task class.

    We assign _Taskify as the metaclass of all the Task base classes, so that all user-defined derived classes of those
    will also inherit the metaclass.

    See https://realpython.com/python-metaclasses/ for more information on metaclasses.
    """

    def __new__(cls, name: str, bases: tuple[type], attrs: dict[str, Any]) -> type:
        """
        __new__ is called when a new class is created (derived from Task). We can use this to perform some validation
        on the class definition and to generate a unique identifier for the task.

        Args:
            name: The name of the user defined class.
            bases: Tuple of base classes.
            attrs: Attributes of the user defined class, such as methods and class variables.

        Returns:
            type: The newly created class.
        """
        task_class = super().__new__(cls, name, bases, attrs)
        # without any bases we are handling the Task class itself, and not user-defined subclasses
        if len(bases) == 0:
            return task_class

        # Convert the class to a dataclass
        task_class = dataclass(task_class)

        # we allow overriding the execute method, but we still want to validate it
        # so we search for the closest base class that has an execute method and use
        # that to validate the execute method of the current class. We know the base
        # class is valid, because it has to be defined and validated to be able to use
        # it as a base class for a task.
        base_execute = None
        for base in bases[::-1]:
            base_execute = getattr(base, "execute", None)
            if base_execute is not None:
                break

        if base_execute is None:
            raise TypeError("_Taskify metaclass can only be used in combination with an execute method")

        is_executable = _validate_execute_method(name, attrs, inspect.signature(base_execute))
        try:
            identifier = _get_task_identifier(task_class)
        except ValueError as err:
            # raise as TypeError instead of a ValueError, because this runs at class creation time
            raise TypeError(str(err)) from None

        setattr(task_class, META_ATTR, TaskMeta(identifier, is_executable))
        return task_class


class _ABCTaskify(ABCMeta, _Taskify):  # the order here is actually relevant: ABCMeta will run first, and then _Taskify
    """A metaclass which combines abstract base class functionality with our own _Taskify metaclass.

    This is necessary to resolve the metaclass conflict between ABCMeta and _Taskify in case a task inherits
    from an abstract base class
    """


# This is a neat typing feature: If dataclass_transform is applied to a class, dataclass-like semantics will be
# assumed for any class that directly or indirectly derives from the decorated class or uses the decorated class
# as a metaclass. Attributes on the decorated class and its base classes are not considered to be fields.
# See https://peps.python.org/pep-0681/
@dataclass_transform()
class Task(metaclass=_ABCTaskify):
    """A Tilebox workflows task.

    This is the base class that provides the basic structure and functionality for a task.

    This class is a dataclass. The task is automatically assigned an identifier based on the class name.
    """

    def execute(self, context: "ExecutionContext") -> Awaitable[None] | None:
        """The entry point for the execution of the task.

        It is called when the task is executed and is responsible for performing the task's operation.
        A fresh task instance and execution context are created for every execution. Worker runtimes may execute
        multiple tasks concurrently on different threads, and asynchronous tasks may use different event loops.
        Mutable class or module state, runner context state, and custom caches must be safe for concurrent access.

        Args:
            context: The execution context for the task. It provides access to an API for submitting new tasks as part
                of the same job, as well as access to a shared cache and features such as logging.
        """

    def _serialize(self) -> bytes:
        return serialize_task(self)

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> "Task":  # noqa: ARG003
        return deserialize_task(cls, task_input)


def _validate_execute_method(
    class_name: str, attrs: dict[str, Any], expected_execute_signature: inspect.Signature
) -> bool:
    """Perform some validation on the execute method of a task class."""
    if "execute" not in attrs:
        return False

    execute = attrs["execute"]

    if getattr(execute, "__override__", False):
        return True  # if we explicitly override the execute method, we don't validate it

    signature = inspect.signature(execute)
    if len(signature.parameters) != len(expected_execute_signature.parameters):
        raise TypeError(
            f"Expected a function signature of {class_name}.execute{expected_execute_signature}, "
            f"but got {class_name}.execute{signature}!"
        )

    return_annotation = signature.return_annotation
    with suppress(NameError, TypeError):
        return_annotation = typing.get_type_hints(execute).get("return", return_annotation)

    if not _is_valid_execute_return_annotation(return_annotation):
        raise TypeError(f"Expected {class_name}.execute{signature} to not have a return value!")

    return True


def _is_valid_execute_return_annotation(annotation: Any) -> bool:
    if annotation in (None, NoneType, "None", "Awaitable[None]", inspect.Signature.empty):
        return True

    origin = get_origin(annotation)
    if origin in (typing.Union, UnionType):
        return all(_is_valid_execute_return_annotation(member) for member in get_args(annotation))

    if not isinstance(origin, type) or not issubclass(origin, Awaitable):
        return False

    result_types = get_args(annotation)
    return bool(result_types) and result_types[-1] in (None, NoneType)


@dataclass
class TaskMeta:
    identifier: TaskIdentifier
    executable: bool

    @staticmethod
    def for_task(task: type | Task) -> "TaskMeta":
        """Get the task metadata for a specific task class.

        Args:
            task: The task or task class to get the metadata for.

        Returns:
            Task metadata
        """
        return _task_meta(task)


def _task_meta(task_or_task_execution: type | Task) -> TaskMeta:
    """Get the task metadata for a task class or task instance.

    Args:
        task_or_task_execution: The task class or task instance to get the metadata for.

    Raises:
        TypeError: If the given argument is not a task or task instance.

    Returns:
        The task metadata.
    """
    cls = task_or_task_execution if isinstance(task_or_task_execution, type) else type(task_or_task_execution)

    meta: TaskMeta | None = cast(TaskMeta | None, getattr(cls, META_ATTR, None))
    if meta is None or not isinstance(meta, TaskMeta):
        raise TypeError(f"{cls.__name__} is not a task!")
    return meta


def _get_task_identifier(task_class: type) -> TaskIdentifier:
    """Get the task identifier for a task class.

    Invokes a user-defined identifier method if it exists, or generates default identifier otherwise.
    An example of how a user defined task identifier (that's recognized by this method) could be used:

    class MyTask(Task):
        @staticmethod
        def identifier() -> tuple[str, str]:
            return ("tilebox.workflows.MyTask", "v3.2")

    If no identifier method is defined, we generate a default identifier based on the class name and version "v0.0".
    """
    class_name = task_class.__name__
    if hasattr(task_class, "identifier"):  # if the task class has an identifier method, we use that
        try:
            name, version = task_class.identifier()  # ty: ignore[call-non-callable]
        except TypeError as err:
            raise ValueError(
                f"Failed to invoke {class_name}.identifier(). Is it a staticmethod or classmethod without parameters?"
            ) from err
        except ValueError as err:
            raise ValueError(f"Expected {class_name}.identifier() to return a tuple of two strings") from err
        if not isinstance(name, str) or not isinstance(version, str):
            raise ValueError(f"Expected {class_name}.identifier() to return a tuple of two strings")

    else:  # if no identifier method is defined, we generate a default identifier
        name = class_name
        version = "v0.0"

    return TaskIdentifier.from_name_and_version(name, version)


@dataclass
class FutureTask:
    """A task that we will submit as a subtask with the completion of the current task."""

    index: int
    task: Task
    depends_on: list[int]
    cluster: str | None
    max_retries: int
    optional: bool

    def identifier(self) -> TaskIdentifier:
        return _task_meta(self.task).identifier

    def input(self) -> bytes:
        return self.task._serialize()  # noqa: SLF001

    def display(self) -> str:
        return self.task.__class__.__name__


_T = TypeVar("_T")


class _FastIndexLookupList(Generic[_T]):
    """A list that provides fast lookup by index."""

    def __init__(self) -> None:
        super().__init__()
        self.values = []
        self._index_lookup: dict[_T, int] = {}

    def __contains__(self, key: _T) -> bool:
        return key in self._index_lookup

    def __getitem__(self, key: _T) -> _T:
        index = self._index_lookup[key]
        return self.values[index]

    def append_if_unique(self, value: _T) -> int:
        if value in self._index_lookup:
            return self._index_lookup[value]
        index = len(self.values)
        self.values.append(value)
        self._index_lookup[value] = index
        return index


def merge_future_tasks_to_submissions(future_tasks: list[FutureTask], fallback_cluster: str) -> TaskSubmissions | None:
    if len(future_tasks) == 0:
        return None

    dependants = defaultdict(set)
    for task in future_tasks:
        for dep in task.depends_on:
            dependants[dep].add(task.index)

    dependants = {k: frozenset(v) for k, v in dependants.items()}

    # we keep track of which task ends up in which group, so we can convert task dependencies to group dependencies
    task_index_to_group = {}

    group_keys = _FastIndexLookupList[_TaskGroupUniqueKey]()
    groups: list[TaskSubmissionGroup] = []
    # even though in python dicts preserve insertion order, we explicitly keep a list and an explicit lookup dict, to
    # make the intent clear. This also allows us to more easily port this code to Tilebox clients in other languages.
    cluster_slugs = _FastIndexLookupList[str]()
    identifiers = _FastIndexLookupList[TaskIdentifier]()
    displays = _FastIndexLookupList[str]()

    for task in future_tasks:
        group_key = _TaskGroupUniqueKey(
            dependencies=frozenset(task.depends_on),
            dependants=dependants.get(task.index, frozenset()),
        )
        group_index = group_keys.append_if_unique(group_key)
        if group_index == len(groups):  # it was a new unique group
            groups.append(TaskSubmissionGroup(dependencies_on_other_groups=task.depends_on))
        task_index_to_group[task.index] = group_index

    for i in range(len(groups)):
        group = groups[i]
        group.dependencies_on_other_groups = list(
            # convert the task dependencies to group dependencies, deduplicate and sort them
            {task_index_to_group[dep] for dep in group.dependencies_on_other_groups}
        )

    for task in future_tasks:
        group_index = task_index_to_group[task.index]
        group = groups[group_index]

        group.inputs.append(task.input())
        group.identifier_pointers.append(identifiers.append_if_unique(task.identifier()))
        group.cluster_slug_pointers.append(cluster_slugs.append_if_unique(task.cluster or fallback_cluster))
        group.display_pointers.append(displays.append_if_unique(task.display()))
        group.max_retries_values.append(task.max_retries)
        group.optional_values.append(task.optional)

    return TaskSubmissions(
        task_groups=groups,
        cluster_slug_lookup=cluster_slugs.values,
        identifier_lookup=identifiers.values,
        display_lookup=displays.values,
    )


@dataclass(frozen=True, unsafe_hash=True)
class _TaskGroupUniqueKey:
    dependencies: frozenset[int]
    dependants: frozenset[int]


class ProgressUpdate:
    def __init__(self, label: str | None) -> None:
        self._label = label
        self._total = 0
        self._done = 0

    def add(self, count: int) -> None:
        """Add a given amount of total work to be done to the progress indicator.

        Args:
            count: The amount of work to add to the progress indicator.
        """
        self._total += count

    def done(self, count: int) -> None:
        """Mark a given amount of work as done.

        Args:
            count: The amount of work to mark as done.
        """
        self._done += count


class ExecutionContext(ABC):
    """The execution context for a task."""

    @abstractmethod
    def submit_subtask(
        self,
        task: Task,
        depends_on: FutureTask | list[FutureTask] | None = None,
        cluster: str | None = None,
        max_retries: int = 0,
        optional: bool = False,
    ) -> FutureTask:
        """Submit a subtask of the current task.

        Args:
            task: The subtask to submit.
            depends_on: List of other subtasks, previously submitted within the same task context, that this subtask
                depends on. Defaults to None.
            cluster: Slug of the cluster to submit the subtask to. Defaults to None, which means the same cluster as the
                task runner will be used.
            max_retries: The maximum number of retries for the subtask in case of failure. Defaults to 0.
            optional: Whether the subtask is optional. If True, the subtask will not fail the job if it fails. Also
                tasks that depend on this task will still execute after this task even if this task failed. Defaults
                to False.

        Returns:
            Submitted subtask.
        """

    @abstractmethod
    def submit_subtasks(
        self,
        tasks: Sequence[Task],
        depends_on: FutureTask | list[FutureTask] | None = None,
        cluster: str | None = None,
        max_retries: int = 0,
        optional: bool = False,
    ) -> list[FutureTask]:
        """Submit a batch of subtasks of the current task. Similar to `submit_subtask`, but for multiple tasks."""

    @abstractmethod
    def submit_batch(self, tasks: Sequence[Task], cluster: str | None = None, max_retries: int = 0) -> list[FutureTask]:
        """Deprecated. Use `submit_subtasks` instead."""

    @property
    @abstractmethod
    def runner_context(self) -> RunnerContext:
        """Get the runner context for the task runner executing the task."""

    @property
    @abstractmethod
    def tracer(self) -> WorkflowTracer:
        """Get the tracer for the task runner executing the task."""

    @property
    @abstractmethod
    def logger(self) -> StructuredLogger:
        """Get the logger for the task runner executing the task."""

    @abstractmethod
    def progress(self, label: str | None = None) -> ProgressUpdate:
        """Get a progress indicator instance for tracking job progress."""


def serialize_task(task: Task) -> bytes:
    """Serialize a task to a buffer of bytes.

    A task is expected to be a dataclass, containing an arbitrary number of fields. Each field can either be a
    primitive type, another dataclass or a protobuf message.

    Serialization is done as json, so the result will be a json string mapping field names to their values.
    However, if only one field is present, it will be serialized directly, without the need for a json string.
    Timezone-aware datetimes retain their offset, while timezone-naive datetimes remain naive.
    """
    if not is_dataclass(task):
        raise TypeError("Cannot serialize the given task - did you inherit from Task?")

    task_fields = [f for f in fields(task) if not f.metadata.get("skip_serialization", False)]
    if len(task_fields) == 0:
        return b""  # empty task
    if len(task_fields) == 1:
        value = getattr(task, task_fields[0].name)
        if hasattr(value, "SerializeToString"):
            return value.SerializeToString()
        return encode_json_field(value, type(task), task_fields[0].name)

    return encode_json_fields(task, task_fields)


_T = TypeVar("_T", bound=Task)


def deserialize_task(task_cls: type[_T], task_input: bytes) -> _T:
    """Deserialize the input of a task from a buffer of bytes.

    The task_cls is expected to be a dataclass, containing an arbitrary number of fields.
    The same deserialization logic as for serialize_task is used.
    """

    task_fields = [f for f in fields(task_cls) if not f.metadata.get("skip_serialization", False)]
    if len(task_fields) == 0:
        return task_cls()  # empty task
    if len(task_fields) == 1:
        # if there is only one field, we deserialize it directly
        type_hints = typing.get_type_hints(task_cls, include_extras=True)
        field_type = type_hints.get(task_fields[0].name, task_fields[0].type)
        protobuf_type = _get_deserialization_field_type(field_type)
        if hasattr(protobuf_type, "FromString"):  # protobuf message
            value = None if task_input == b"null" else protobuf_type.FromString(task_input)  # ty: ignore[call-non-callable]
        else:
            value = decode_json(task_input, field_type)

        return task_cls(**{task_fields[0].name: value})

    return decode_json(task_input, task_cls)


def _get_deserialization_field_type(field_type: type) -> type:
    """
    Get the actual underlying type we want to deserialize a field type annotated as.

    This correctly handles optional and annotated type hints.

    For example, all of the following fields should be deserialized as MyDataclass class

    field1: MyDataclass
    field2: MyDataclass | None
    field3: Optional[MyDataclass]
    field4: Annotated[MyDataclass, "some description"]
    field5: Annotated[Optional[MyDataclass], "some description"
    """
    origin = typing.get_origin(field_type)
    if origin in (typing.Union, UnionType):  # handle Optional[type] and 'type | None'
        args = typing.get_args(field_type)
        if len(args) == 2 and args[-1] == NoneType:
            return _get_deserialization_field_type(args[0])
    if origin == typing.Annotated:
        args = typing.get_args(field_type)
        if len(args) >= 1:
            return _get_deserialization_field_type(args[0])

    return field_type
