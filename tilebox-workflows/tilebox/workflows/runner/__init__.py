from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tilebox.workflows.runner.runner import Runner
    from tilebox.workflows.runner.task_runner import TaskRunner

__all__ = ["Runner", "TaskRunner"]


def __getattr__(name: str) -> Any:
    # PEP 562 module __getattr__ is supported since Python 3.7.
    match name:
        case "Runner":
            from tilebox.workflows.runner.runner import Runner  # noqa: PLC0415

            value = Runner
        case "TaskRunner":
            from tilebox.workflows.runner.task_runner import TaskRunner  # noqa: PLC0415

            value = TaskRunner
        case _:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    # Cache the resolved export so subsequent access uses normal module lookup instead of calling __getattr__ again.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    # Include public lazy exports in dir(module) before they have been loaded.
    return sorted(set(globals()) | set(__all__))
