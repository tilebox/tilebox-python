from _tilebox.grpc.aio.syncify import _syncify_coroutine
from tilebox.datasets.data import TimeInterval
from tilebox.workflows.timeseries.timeseries import SyncTimeIntervalTask as TimeIntervalTask
from tilebox.workflows.timeseries.timeseries import SyncTimeseriesTask as TimeseriesTask
from tilebox.workflows.timeseries.timeseries import batch_process_time_interval
from tilebox.workflows.timeseries.timeseries import (
    batch_process_timeseries_dataset as _batch_process_timeseries_dataset,
)

batch_process_timeseries_dataset = _syncify_coroutine(_batch_process_timeseries_dataset)


__all__ = ["TimeIntervalTask", "TimeseriesTask", "TimeInterval", "batch_process_time_interval"]
