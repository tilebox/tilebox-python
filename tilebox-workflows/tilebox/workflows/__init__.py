import os
import sys

from loguru import logger

from _tilebox.grpc.aio.syncify import T_Syncifiable as _T_Syncifiable
from tilebox.workflows.clients.client import Client as _AsyncClient
from tilebox.workflows.task import ExecutionContext
from tilebox.workflows.task import SyncTask as Task


class Client(_AsyncClient):
    """A client that can be used to access the tilebox workflows service."""

    def __init__(self, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        super().__init__(url, token)
        self._syncify()

    def _subclient(self, subclient: _T_Syncifiable) -> _T_Syncifiable:
        subclient._syncify()  # noqa: SLF001
        return subclient


__all__ = ["Client", "Task", "ExecutionContext"]


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
