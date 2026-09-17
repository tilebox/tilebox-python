import os
from typing import TYPE_CHECKING, Any

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


def _initialize_logging_from_environment() -> None:
    # Stage 1: current CLIs provide credentials before importing workflow code, so
    # even import-time logs reach the API. Ordinary SDK imports stay lightweight.
    url = os.environ.get("TILEBOX_API_URL")
    token = os.environ.get("TILEBOX_API_KEY")
    if not url or not token:
        return

    from tilebox.workflows.observability.logging import initialize_logging  # noqa: PLC0415

    initialize_logging(url=url, token=token)


_initialize_logging_from_environment()
