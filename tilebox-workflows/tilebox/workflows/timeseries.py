import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import pairwise

import xarray as xr

# from python 3.11 onwards: typing.dataclass_transform
# from python 3.12 onwards: typing.override
from typing_extensions import dataclass_transform, override

from tilebox.datasets.data.collection import Collection, CollectionInfo
from tilebox.datasets.data.timeseries import TimeChunk, TimeseriesDatasetChunk
from tilebox.datasets.query.id_interval import IDInterval
from tilebox.datasets.query.time_interval import TimeInterval, TimeIntervalLike
from tilebox.datasets.sync.dataset import CollectionClient
from tilebox.workflows.interceptors import ForwardExecution, execution_interceptor
from tilebox.workflows.task import ExecutionContext, Task

_365_DAYS = timedelta(days=365)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@execution_interceptor
def _timeseries_dataset_chunk(task: Task, call_next: ForwardExecution, context: ExecutionContext) -> None:  # noqa: C901
    if not isinstance(task, TimeseriesTask):
        raise TypeError("Task is not a timeseries task. Inherit from TimeseriesTask to mark it as such.")

    chunk: TimeseriesDatasetChunk = task.timeseries_data  # type: ignore[attr-defined]

    # let's get a collection client
    datasets_client = context.runner_context.datasets_client
    dataset = datasets_client._dataset_by_id(str(chunk.dataset_id))  # type: ignore[attr-defined]  # noqa: SLF001
    # we already know the collection id, so we can skip the lookup (we don't know the name, but don't need it)
    collection_info = CollectionInfo(Collection(chunk.collection_id, "unknown"), None, None)
    collection = CollectionClient(dataset, collection_info)

    # leaf case: we are already executing a specific batch of datapoints fitting in the chunk size, so let's load them
    if chunk.datapoint_interval:
        datapoint_interval = (chunk.datapoint_interval.start_id, chunk.datapoint_interval.end_id)
        # we already are a leaf task executing for a specific datapoint interval:
        datapoints = collection._find_interval(  # noqa: SLF001
            datapoint_interval,
            end_inclusive=chunk.datapoint_interval.end_inclusive,
            skip_data=False,
            show_progress=False,
        )
        if not datapoints:
            return  # no datapoints in the interval -> we are done

        for i in range(datapoints.sizes["time"]):
            datapoint = datapoints.isel(time=i)
            call_next(context, datapoint)  # type: ignore[call-arg]

        return  # we are done

    if not chunk.time_interval:
        raise ValueError("Missing time_interval and data_point interval, one of them is required")

    interval = chunk.time_interval
    interval_size = interval.end - interval.start
    estimated_datapoints = int(chunk.datapoints_per_365_days * (interval_size / _365_DAYS))
    sub_chunks = []

    # if we are only a little larger than the chunk size, let's submit leaf tasks next:
    if estimated_datapoints < chunk.chunk_size * (chunk.branch_factor - 0.5):
        for page in collection._iter_pages(  # noqa: SLF001
            interval, skip_data=True, show_progress=False, page_size=chunk.chunk_size
        ):
            # pages here only contain datapoint ids, no metadata or data
            # pages are limited to a maximum of chunk_size datapoints, but additionally also server side
            # in case the chunk size is larger than the server side maximum limit
            # in that case we just use an effective chunk size of the server side limit

            if page.n_datapoints > 0:
                interval_chunk = replace(
                    chunk,
                    time_interval=None,
                    datapoint_interval=IDInterval(
                        start_id=page.min_id, end_id=page.max_id, start_exclusive=False, end_inclusive=True
                    ),
                )
                sub_chunks.append(interval_chunk)

    # otherwise let's split our time range evenly into sub chunks:
    else:
        chunk_interval = interval_size / chunk.branch_factor
        chunks = [chunk.time_interval.start + chunk_interval * i for i in range(chunk.branch_factor)] + [interval.end]

        for sub_chunk_start, sub_chunk_end in pairwise(chunks):
            sub_chunks.append(replace(chunk, time_interval=TimeInterval(sub_chunk_start, sub_chunk_end)))

    subtasks = [replace(task, timeseries_data=sub_chunk) for sub_chunk in sub_chunks]  # type: ignore[misc]
    if len(subtasks) > 0:
        context.submit_subtasks(subtasks)

    return


@_timeseries_dataset_chunk
@dataclass_transform()
class TimeseriesTask(Task):
    timeseries_data: TimeseriesDatasetChunk

    @override
    def execute(self, context: ExecutionContext, datapoint: xr.Dataset) -> None:  # type: ignore[override]
        pass


def batch_process_timeseries_dataset(
    collection: CollectionClient, interval: TimeIntervalLike, chunk_size: int
) -> TimeseriesDatasetChunk:
    info = collection.info(availability=True, count=True)

    assert info.availability is not None
    assert info.count is not None

    interval = TimeInterval.parse(interval).to_half_open()  # our time splitting assumes half open intervals

    # estimate the number of datapoints per 365 days, to roughly know when to stop splitting into branches
    datapoints_per_365_days = math.ceil(info.count / ((info.availability.end - info.availability.start) / _365_DAYS))

    return TimeseriesDatasetChunk(
        dataset_id=collection._dataset._dataset.id,  # noqa: SLF001
        collection_id=info.collection.id,
        time_interval=interval,
        datapoint_interval=None,
        branch_factor=2,
        chunk_size=chunk_size,
        datapoints_per_365_days=datapoints_per_365_days,
    )


@execution_interceptor
def _time_interval_chunk(task: Task, call_next: ForwardExecution, context: ExecutionContext) -> None:
    if not isinstance(task, TimeIntervalTask):
        raise TypeError("Task is not a time interval task. Inherit from TimeIntervalTask to mark it as such.")

    chunk: TimeChunk = task.interval  # type: ignore[attr-defined]

    start = _make_multiple(chunk.time_interval.start, chunk.chunk_size, before=True)
    end = _make_multiple(chunk.time_interval.end, chunk.chunk_size, before=False)

    n = (end - start) // chunk.chunk_size
    if n <= 1:  # we are already a leaf task
        return call_next(context, TimeInterval(start, end))  # type: ignore[call-arg]

    chunks: list[datetime] = []
    if n < 4:  # we are a branch task with less than 4 sub chunks, so a further split is not worth it
        chunks = [start + chunk.chunk_size * i for i in range(n)] + [end]
    else:  # we have a large number of sub chunks, so let's split into 2 branches
        # in case we can't perfectly divide in the middle due to an uneven
        # number make the left half slightly larger than the right half
        middle = _make_multiple(start + (end - start) / 2, chunk.chunk_size, before=False)
        chunks = [start, middle, end]

    time_chunks = [
        TimeChunk(TimeInterval(chunk_start, chunk_end), chunk.chunk_size) for chunk_start, chunk_end in pairwise(chunks)
    ]

    context.submit_subtasks(
        [replace(task, interval=time_chunk) for time_chunk in time_chunks]  # type: ignore[misc]
    )
    return None


@_time_interval_chunk
@dataclass_transform()
class TimeIntervalTask(Task):
    interval: TimeChunk

    @override
    def execute(self, context: ExecutionContext, time_interval: TimeInterval) -> None:  # type: ignore[override]
        pass


def batch_process_time_interval(interval: TimeIntervalLike, chunk_size: timedelta) -> TimeChunk:
    return TimeChunk(time_interval=TimeInterval.parse(interval).to_half_open(), chunk_size=chunk_size)  # type: ignore[arg-type]


def _make_multiple(time: datetime, duration: timedelta, start: datetime = _EPOCH, before: bool = True) -> datetime:
    """
    Calculate the nearest multiple of a duration for a given datetime relative to the given start datetime.

    Depending on the before argument, this will calculate the nearest multiple immediately before or after the given
    time.

    >>> _make_multiple(datetime(2021, 4, 13, 13, 12, 10), timedelta(days=1))
    datetime.datetime(2021, 4, 13, 0, 0)

    >>> _make_multiple(datetime(2021, 4, 13, 13, 12, 10), timedelta(days=1), before=False)
    datetime.datetime(2021, 4, 14, 0, 0)

    Args:
        time: The datetime to make a multiple.
        duration: The duration to make a multiple of.
        start: The start datetime to make a multiple relative to. Defaults to _EPOCH.
        before: Whether to calculate the nearest multiple immediately before or after the given time. Defaults to True.

    Returns:
        A datetime that is a multiple of the given duration relative to the given start datetime.
    """
    n = (time - start) / duration
    n = math.floor(n) if before else math.ceil(n)
    return start + n * duration
