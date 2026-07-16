import os
import sys
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from tilebox.datasets.aio.timeseries import TimeseriesCollection, TimeseriesDataset
    from tilebox.datasets.sync.client import Client
    from tilebox.datasets.sync.dataset import CollectionClient, DatasetClient

__all__ = ["Client", "CollectionClient", "DatasetClient", "TimeseriesCollection", "TimeseriesDataset"]


def __getattr__(name: str) -> Any:
    # PEP 562 module __getattr__ is supported since Python 3.7. Keep these aliases lazy so importing a focused
    # submodule like tilebox.datasets.query.id_interval does not also import the sync/aio clients and their data-model
    # dependencies.
    match name:
        case "Client":
            from tilebox.datasets.sync.client import Client  # noqa: PLC0415

            value = Client
        case "CollectionClient":
            from tilebox.datasets.sync.dataset import CollectionClient  # noqa: PLC0415

            value = CollectionClient
        case "DatasetClient":
            from tilebox.datasets.sync.dataset import DatasetClient  # noqa: PLC0415

            value = DatasetClient
        case "TimeseriesCollection":
            from tilebox.datasets.aio.timeseries import TimeseriesCollection  # noqa: PLC0415

            value = TimeseriesCollection
        case "TimeseriesDataset":
            from tilebox.datasets.aio.timeseries import TimeseriesDataset  # noqa: PLC0415

            value = TimeseriesDataset
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
