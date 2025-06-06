import os
import sys

from loguru import logger

from tilebox.datasets.aio import Client as _AsyncClient


class Client(_AsyncClient):
    def __init__(self, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        super().__init__(url, token)
        self._syncify()


__all__ = ["Client"]


def _init_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stdout, level=level, format="{message}", catch=True)


def _is_debug() -> bool:
    try:
        return bool(int(os.environ.get("TILEBOX_DEBUG") or 0))
    except (TypeError, ValueError):
        return False


if _is_debug():
    _init_logging("DEBUG")
else:
    _init_logging()
