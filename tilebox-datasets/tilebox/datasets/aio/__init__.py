from tilebox.datasets.aio.client import Client
from tilebox.datasets.aio.dataset import CollectionClient, DatasetClient

# only here for backwards compatibility, to preserve backwards compatibility with older imports
from tilebox.datasets.aio.timeseries import TimeseriesCollection, TimeseriesDataset

__all__ = ["Client", "CollectionClient", "DatasetClient", "TimeseriesCollection", "TimeseriesDataset"]
