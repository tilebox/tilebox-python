import os
import sys
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from tilebox.workflows.client import Client
    from tilebox.workflows.data import Job
    from tilebox.workflows.runner.runner import Runner
    from tilebox.workflows.task import ExecutionContext, Task

__all__ = ["Client", "ExecutionContext", "Job", "Runner", "Task"]


def __getattr__(name: str) -> Any:
    match name:
        case "Client":
            from tilebox.workflows.client import Client  # noqa: PLC0415

            value = Client
        case "ExecutionContext":
            from tilebox.workflows.task import ExecutionContext  # noqa: PLC0415

            value = ExecutionContext
        case "Job":
            from tilebox.workflows.data import Job  # noqa: PLC0415

            value = Job
        case "Runner":
            from tilebox.workflows.runner.runner import Runner  # noqa: PLC0415

            value = Runner
        case "Task":
            from tilebox.workflows.task import Task  # noqa: PLC0415

            value = Task
        case _:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    # Cache the resolved export so subsequent access uses normal module lookup instead of calling __getattr__ again.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    # Include public lazy exports in dir(module) before they have been loaded.
    return sorted(set(globals()) | set(__all__))


def _init_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stdout, level=level, format="{process}: {level}: {message}", catch=True)


def _is_debug() -> bool:
    try:
        return bool(int(os.environ.get("TILEBOX_DEBUG") or 0))
    except (TypeError, ValueError):
        return False


if _is_debug():
    _init_logging("DEBUG")
else:
    _init_logging()
