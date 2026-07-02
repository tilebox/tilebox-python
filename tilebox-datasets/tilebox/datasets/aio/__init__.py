from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tilebox.datasets.aio.client import Client
    from tilebox.datasets.aio.dataset import CollectionClient, DatasetClient
    from tilebox.datasets.aio.timeseries import TimeseriesCollection, TimeseriesDataset

__all__ = ["Client", "CollectionClient", "DatasetClient", "TimeseriesCollection", "TimeseriesDataset"]


def __getattr__(name: str) -> Any:
    # PEP 562 module __getattr__ is supported since Python 3.7. Keep these aliases lazy so importing
    # tilebox.datasets.aio does not also import xarray/pandas-backed dataset clients.
    match name:
        case "Client":
            from tilebox.datasets.aio.client import Client  # noqa: PLC0415

            value = Client
        case "CollectionClient":
            from tilebox.datasets.aio.dataset import CollectionClient  # noqa: PLC0415

            value = CollectionClient
        case "DatasetClient":
            from tilebox.datasets.aio.dataset import DatasetClient  # noqa: PLC0415

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
