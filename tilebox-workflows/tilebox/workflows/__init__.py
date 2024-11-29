import os
import sys

from loguru import logger

from tilebox.workflows.client import Client
from tilebox.workflows.task import ExecutionContext, Task

__all__ = ["Client", "ExecutionContext", "Task"]


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
