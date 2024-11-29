import os
import sys

from loguru import logger

from tilebox.datasets.sync.client import Client
from tilebox.datasets.sync.timeseries import TimeseriesCollection, TimeseriesDataset

__all__ = ["Client", "TimeseriesCollection", "TimeseriesDataset"]


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
