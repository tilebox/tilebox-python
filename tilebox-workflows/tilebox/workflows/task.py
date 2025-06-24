import contextlib
import inspect
import json
from abc import ABC, ABCMeta, abstractmethod
from base64 import b64decode, b64encode
from collections.abc import Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, cast, get_args, get_origin

# from python 3.11 onwards this is available as typing.dataclass_transform:
from typing_extensions import dataclass_transform

from tilebox.workflows.data import RunnerContext, TaskIdentifier, TaskSubmission

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
        task_class = dataclass(task_class)  # type: ignore[arg-type]

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

        interceptors = []
        with contextlib.suppress(TypeError):
            # if possible we copy the already existing interceptors from the base class
            interceptors = list(_task_meta(bases[-1]).interceptors)

        setattr(task_class, META_ATTR, TaskMeta(identifier, is_executable, interceptors))
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

    def execute(self, context: "ExecutionContext") -> None:
        """The entry point for the execution of the task.

        It is called when the task is executed and is responsible for performing the task's operation.

        Args:
            context: The execution context for the task. It provides access to an API for submitting new tasks as part
                of the same job, as well as access to a shared cache and features such as logging.
        """

    def _serialize(self) -> bytes:
        return serialize_task(self)

    @classmethod
    def _deserialize(cls, task_input: bytes, context: RunnerContext | None = None) -> "Task":  # noqa: ARG003
        return cast(Task, deserialize_task(cls, task_input))


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

    if signature.return_annotation is not None and signature.return_annotation != inspect._empty:  # noqa: SLF001
        raise TypeError(f"Expected {class_name}.execute{signature} to not have a return value!")

    return True


@dataclass
class TaskMeta:
    identifier: TaskIdentifier
    executable: bool
    interceptors: list[Any] = field(default_factory=list)

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
            name, version = task_class.identifier()
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

    def identifier(self) -> TaskIdentifier:
        return _task_meta(self.task).identifier

    def input(self) -> bytes:
        return self.task._serialize()  # noqa: SLF001

    def display(self) -> str:
        return self.task.__class__.__name__

    def to_submission(self, fallback_cluster: str = "") -> TaskSubmission:
        return TaskSubmission(
            cluster_slug=self.cluster or fallback_cluster,
            identifier=self.identifier(),
            input=self.input(),
            display=self.display(),
            dependencies=self.depends_on,
            max_retries=self.max_retries,
        )


class ExecutionContext(ABC):
    """The execution context for a task."""

    @abstractmethod
    def submit_subtask(
        self, task: Task, depends_on: list[FutureTask] | None = None, cluster: str | None = None, max_retries: int = 0
    ) -> FutureTask:
        """Submit a subtask of the current task.

        Args:
            task: The subtask to submit.
            depends_on: List of other subtasks, previously submitted within the same task context, that this subtask
                depends on. Defaults to None.
            cluster: Slug of the cluster to submit the subtask to. Defaults to None, which means the same cluster as the
                task runner will be used.
            max_retries: The maximum number of retries for the subtask in case of failure. Defaults to 0.

        Returns:
            Submitted subtask.
        """

    @abstractmethod
    def submit_subtasks(
        self, tasks: Sequence[Task], cluster: str | None = None, max_retries: int = 0
    ) -> list[FutureTask]:
        """Submit a batch of subtasks of the current task. Similar to `submit_subtask`, but for multiple tasks."""

    @abstractmethod
    def submit_batch(self, tasks: Sequence[Task], cluster: str | None = None, max_retries: int = 0) -> list[FutureTask]:
        """Deprecated. Use `submit_subtasks` instead."""

    @property
    @abstractmethod
    def runner_context(self) -> RunnerContext:
        """Get the runner context for the task runner executing the task."""


def serialize_task(task: Task) -> bytes:
    """Serialize a task to a buffer of bytes.

    A task is expected to be a dataclass, containing an arbitrary number of fields. Each field can either be a
    primitive type, another dataclass or a protobuf message.

    Serialization is done as json, so the result will be a json string mapping field names to their values.
    However, if only one field is present, it will be serialized directly, without the need for a json string.
    """
    if not is_dataclass(task):
        raise TypeError("Cannot serialize the given task - did you inherit from Task?")

    task_fields = [f for f in fields(task) if not f.metadata.get("skip_serialization", False)]
    if len(task_fields) == 0:
        return b""  # empty task
    if len(task_fields) == 1:
        # if there is only one field, we can serialize it directly
        field = _serialize_value(getattr(task, task_fields[0].name), base64_encode_protobuf=False)
        if not isinstance(field, bytes):
            field = json.dumps(field).encode()
        return field

    return json.dumps(_serialize_as_dict(task)).encode()  # type: ignore[arg-type]


def _serialize_as_dict(task: Task) -> dict[str, Any]:
    as_dict: dict[str, Any] = {}
    for dataclass_field in fields(task):  # type: ignore[union-attr]
        skip = dataclass_field.metadata.get("skip_serialization", False)
        if skip:
            continue

        as_dict[dataclass_field.name] = _serialize_value(
            getattr(task, dataclass_field.name), base64_encode_protobuf=True
        )

    return as_dict


def _serialize_value(value: Any, base64_encode_protobuf: bool) -> Any:  # noqa: PLR0911
    if isinstance(value, list):
        return [_serialize_value(v, base64_encode_protobuf) for v in value]
    if isinstance(value, tuple):
        return tuple(_serialize_value(v, base64_encode_protobuf) for v in value)
    if isinstance(value, dict):
        # avoid serializing the dict keys, since nested dicts are not valid keys in dicts
        return {k: _serialize_value(v, base64_encode_protobuf) for k, v in value.items()}
    if hasattr(value, "SerializeToString"):  # protobuf message
        if base64_encode_protobuf:
            return b64encode(value.SerializeToString()).decode("ascii")
        return value.SerializeToString()
    if is_dataclass(value):
        return _serialize_as_dict(value)  # type: ignore[arg-type]
    return value


def deserialize_task(task_cls: type, task_input: bytes) -> Task:
    """Deserialize the input of a task from a buffer of bytes.

    The task_cls is expected to be a dataclass, containing an arbitrary number of fields.
    The same deserialization logic as for serialize_task is used.
    """

    task_fields = [f for f in fields(task_cls) if not f.metadata.get("skip_serialization", False)]
    if len(task_fields) == 0:
        return task_cls()  # empty task
    if len(task_fields) == 1:
        # if there is only one field, we deserialize it directly
        field_type = task_fields[0].type
        if hasattr(field_type, "FromString"):  # protobuf message
            value = field_type.FromString(task_input)  # type: ignore[arg-type]
        else:
            value = _deserialize_value(field_type, json.loads(task_input.decode()))  # type: ignore[arg-type]

        return task_cls(**{task_fields[0].name: value})

    return _deserialize_dataclass(task_cls, json.loads(task_input.decode()))


def _deserialize_dataclass(cls: type, params: dict[str, Any]) -> Task:
    """Deserialize a dataclass, while allowing recursively nested dataclasses or protobuf messages."""
    for param in list(params):
        # recursively deserialize nested dataclasses
        field = cls.__dataclass_fields__[param]
        params[field.name] = _deserialize_value(field.type, params[field.name])

    return cls(**params)


def _deserialize_value(field_type: type, value: Any) -> Any:  # noqa: PLR0911
    if hasattr(field_type, "FromString"):
        return field_type.FromString(b64decode(value))
    if is_dataclass(field_type) and isinstance(value, dict):
        return _deserialize_dataclass(field_type, value)

    # in case our field type is a list or dict, we need to recursively deserialize the values
    origin_type = get_origin(field_type)
    if not origin_type:
        return value  # simple type, no further recursion needed

    type_args = get_args(field_type)  # the wrapped type in a container, e.g. list[str] -> type_args is (str,)

    if isinstance(value, list) and origin_type is list and len(type_args) == 1:
        return [_deserialize_value(type_args[0], v) for v in value]
    if isinstance(value, list) and origin_type is tuple:
        # tuples are serialized as json list, so we get a list back
        # which we want to convert back to a tuple
        if len(type_args) == 2 and type_args[1] is Ellipsis:
            type_args = (type_args[0],)  # variadic tuple, we only have one type argument to use for all values
            return tuple(_deserialize_value(type_args[0], v) for v in value)
        return tuple(_deserialize_value(type_args[min(i, len(type_args) - 1)], v) for i, v in enumerate(value))

    if isinstance(value, dict) and origin_type is dict and len(type_args) == 2:
        return {k: _deserialize_value(type_args[1], v) for k, v in value.items()}

    return value
