import functools
from collections.abc import Callable
from typing import Any, Protocol, TypeAlias, cast

from tilebox.workflows.task import ExecutionContext, Task, _task_meta

ForwardExecution: TypeAlias = Callable[[ExecutionContext], Any]


class Interceptor(Protocol):
    def __call__(self, task: Task, call_next: ForwardExecution, context: ExecutionContext) -> None: ...


class InterceptorType(Protocol):
    __original_interceptor_func__: Interceptor

    def __call__(self, task_cls: type) -> type: ...


def execution_interceptor(func: Interceptor) -> InterceptorType:
    """Decorator to convert a function into an execution interceptor.

    Example:
    >>> @execution_interceptor
    >>> def my_interceptor(task: Task, next: Interceptor, context: ExecutionContext) -> None:
    >>>     print("Before")
    >>>     result = next(context)
    >>>     print("After")
    >>>     return result

    Afterwards, my_interceptor can be used as an interceptor in a task definition.
    >>> @my_interceptor
    >>> @task
    >>> class MyTask:
    >>>     ...


    Args:
        func: The function to convert into an interceptor.

    Returns:
        The interceptor function.
    """

    @functools.wraps(func)
    def wrap(task_cls: type) -> type:
        meta = _task_meta(task_cls)
        meta.interceptors.insert(0, func)
        return task_cls

    wrapped: InterceptorType = cast(InterceptorType, wrap)
    # needed internally for task runner interceptors to get the original function
    wrapped.__original_interceptor_func__ = func

    return wrapped


@execution_interceptor
def print_executions(task: Task, call_next: ForwardExecution, context: ExecutionContext) -> None:
    """Print executing tasks."""
    print(f"Executing {task}")  # noqa: T201
    return call_next(context)
