from tilebox.datasets.sync.dataset import CollectionClient as TimeseriesCollection
from tilebox.datasets.sync.dataset import DatasetClient as TimeseriesDataset

# only for for legacy reasons, to preserve backwards compatibility for older imports

__all__ = ["TimeseriesCollection", "TimeseriesDataset"]
