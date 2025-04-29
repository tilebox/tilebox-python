import os
import sys

from loguru import logger

# only here for backwards compatibility, to preserve backwards compatibility with older imports
from tilebox.datasets.aio.timeseries import TimeseriesCollection, TimeseriesDataset
from tilebox.datasets.sync.client import Client
from tilebox.datasets.sync.dataset import CollectionClient, DatasetClient

__all__ = ["Client", "CollectionClient", "DatasetClient", "TimeseriesCollection", "TimeseriesDataset"]


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
