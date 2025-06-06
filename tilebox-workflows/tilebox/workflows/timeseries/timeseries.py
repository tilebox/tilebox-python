import inspect
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from uuid import UUID

import betterproto
import xarray as xr
from betterproto import Message

# from python 3.11 onwards: typing.dataclass_transform
# from python 3.12 onwards: typing.override
from typing_extensions import dataclass_transform, override

from tilebox.datasets.data.collection import Collection, CollectionInfo
from tilebox.datasets.data.time_interval import TimeInterval, TimeIntervalLike
from tilebox.datasets.timeseries import RemoteTimeseriesDatasetCollection
from tilebox.workflows.interceptors import ForwardExecution, execution_interceptor
from tilebox.workflows.task import AsyncTask, ExecutionContext, SyncTask, Task

_365_DAYS = timedelta(days=365)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(eq=False, repr=False)
class _UUID(Message):
    """
    An UUID as a protobuf message.

    This can be used to avoid serializing UUIDs as hex strings, which results in much larger byte
    sequences than necessary.
    """

    uuid: bytes = betterproto.bytes_field(1)  # noqa: RUF009

    def __str__(self) -> str:
        """Convert the UUID bytes back to a hex string."""
        return str(UUID(bytes=self.uuid))

    def __repr__(self) -> str:
        """When displaying it, we act as if it were a UUID string."""
        return '"' + str(self) + '"'

    @classmethod
    def from_str(cls, s: str) -> "_UUID":
        """Convert a hex string to a UUID protobuf message."""
        return cls(uuid=UUID(s).bytes)


@dataclass(eq=False, repr=False)
class _DatapointInterval(Message):
    start: _UUID = betterproto.message_field(1)  # noqa: RUF009
    end: _UUID = betterproto.message_field(2)  # noqa: RUF009


@dataclass(eq=False, repr=False)
class _TimeInterval(Message):
    start_time: datetime = betterproto.message_field(1)  # noqa: RUF009
    end_time: datetime = betterproto.message_field(2)  # noqa: RUF009
    start_exclusive: bool = betterproto.bool_field(3)  # noqa: RUF009
    end_inclusive: bool = betterproto.bool_field(4)  # noqa: RUF009


@dataclass(eq=False, repr=False)
class TimeseriesDatasetChunk(Message):
    dataset_id: _UUID = betterproto.message_field(1)  # noqa: RUF009
    collection_id: _UUID = betterproto.message_field(2)  # noqa: RUF009
    time_interval: _TimeInterval = betterproto.message_field(3)  # noqa: RUF009
    datapoint_interval: _DatapointInterval = betterproto.message_field(4)  # noqa: RUF009
    branch_factor: int = betterproto.int32_field(5)  # noqa: RUF009
    chunk_size: int = betterproto.int32_field(6)  # noqa: RUF009
    datapoints_per_365_days: int = betterproto.int64_field(7)  # noqa: RUF009


@dataclass(eq=False, repr=False)
class TimeChunk(Message):
    time_interval: _TimeInterval = betterproto.message_field(1)  # noqa: RUF009
    chunk_size: timedelta = betterproto.message_field(2)  # noqa: RUF009


@execution_interceptor
async def _timeseries_dataset_chunk(task: Task, call_next: ForwardExecution, context: ExecutionContext) -> None:
    if not isinstance(task, SyncTimeseriesTask | AsyncTimeseriesTask):
        raise TypeError("Task is not a timeseries task. Inherit from TimeseriesTask to mark it as such.")

    chunk: TimeseriesDatasetChunk = task.timeseries_data  # type: ignore[attr-defined]

    # let's get the collection object
    dataset = await context.runner_context.datasets_client.dataset()(str(chunk.dataset_id))  # type: ignore[attr-defined]
    collection = dataset.collection("unknown")  # dummy collection, we will inject the right id below:
    # we already know the collection id, so we can skip the lookup (we don't know the name, but don't need it)
    info = CollectionInfo(Collection(str(chunk.collection_id), "unknown"), None, None)
    collection._info_cache[(False, False)] = info  # noqa: SLF001

    # leaf case: we are already executing a specific batch of datapoints fitting in the chunk size, so let's load them and process them
    if chunk.datapoint_interval:
        datapoint_interval = (str(chunk.datapoint_interval.start), str(chunk.datapoint_interval.end))
        # we already are a leaf task executing for a specific datapoint interval:
        datapoints = await collection._find_interval(  # noqa: SLF001
            datapoint_interval, end_inclusive=True, skip_data=False, show_progress=False
        )
        for i in range(datapoints.sizes["time"]):
            datapoint = datapoints.isel(time=i)
            await call_next(context, datapoint)  # type: ignore[call-arg]

        return  # we are done

    if not chunk.time_interval:
        raise ValueError("Missing time_interval and data_point interval, one of them is required")

    interval = TimeInterval(chunk.time_interval.start_time, chunk.time_interval.end_time)
    interval_size = interval.end - interval.start
    estimated_datapoints = int(chunk.datapoints_per_365_days * (interval_size / _365_DAYS))
    sub_chunks = []

    # if we are only a little larger than the chunk size, let's submit leaf tasks next:
    if estimated_datapoints < chunk.chunk_size * (chunk.branch_factor - 0.5):
        async for page in collection._iter_pages(  # noqa: SLF001
            interval, skip_data=True, skip_meta=True, show_progress=False, page_size=chunk.chunk_size
        ):
            # pages here only contain datapoint ids, no metadata or data
            # pages are limited to a maximum of chunk_size datapoints, but additionally also server side
            # in case the chunk size is larger than the server side maximum limit
            # in that case we just use an effective chunk size of the server side limit

            if len(page.meta) > 0:
                sub_chunks.append(  # noqa: PERF401
                    replace(
                        chunk,
                        time_interval=_TimeInterval(),
                        datapoint_interval=_DatapointInterval(
                            _UUID.from_str(page.meta[0].id), _UUID.from_str(page.meta[-1].id)
                        ),
                    )
                )

    # otherwise let's split our time range evenly into sub chunks:
    else:
        chunk_interval = interval_size / chunk.branch_factor
        chunks = [interval.start + chunk_interval * i for i in range(chunk.branch_factor)] + [interval.end]

        for sub_chunk_start, sub_chunk_end in pairwise(chunks):
            sub_chunks.append(replace(chunk, time_interval=_TimeInterval(sub_chunk_start, sub_chunk_end)))

    subtasks = [replace(task, timeseries_data=sub_chunk) for sub_chunk in sub_chunks]  # type: ignore[misc]
    if len(subtasks) > 0:
        context.submit_batch(subtasks)

    return


@_timeseries_dataset_chunk
@dataclass_transform()
class SyncTimeseriesTask(SyncTask):
    timeseries_data: TimeseriesDatasetChunk

    @override
    def execute(self, context: ExecutionContext, datapoint: xr.Dataset) -> None:  # type: ignore[override]
        pass


@_timeseries_dataset_chunk
@dataclass_transform()
class AsyncTimeseriesTask(AsyncTask):
    timeseries_data: TimeseriesDatasetChunk

    @override
    async def execute(self, context: ExecutionContext, datapoint: xr.Dataset) -> None:  # type: ignore[override]
        pass


async def batch_process_timeseries_dataset(
    collection: RemoteTimeseriesDatasetCollection, interval: TimeIntervalLike, chunk_size: int
) -> TimeseriesDatasetChunk:
    _info = collection.info(availability=True, count=True)
    info: CollectionInfo = await _info if inspect.isawaitable(_info) else _info  # type: ignore[assignment]

    assert info.availability is not None
    assert info.count is not None

    interval = TimeInterval.parse(interval).to_half_open()  # our time splitting assumes half open intervals

    # estimate the number of datapoints per 365 days, to roughly know when to stop splitting into branches
    datapoints_per_365_days = math.ceil(info.count / ((info.availability.end - info.availability.start) / _365_DAYS))

    # convert from one UUID message to another
    dataset_id = _UUID(uuid=collection._dataset._dataset.id.bytes)  # noqa: SLF001

    return TimeseriesDatasetChunk(
        dataset_id=dataset_id,
        collection_id=_UUID.from_str(info.collection.id),
        time_interval=_TimeInterval(interval.start, interval.end, False, False),
        datapoint_interval=_DatapointInterval(),
        branch_factor=2,
        chunk_size=chunk_size,
        datapoints_per_365_days=datapoints_per_365_days,
    )


@execution_interceptor
async def _time_interval_chunk(task: Task, call_next: ForwardExecution, context: ExecutionContext) -> None:
    if not isinstance(task, SyncTimeIntervalTask | AsyncTimeIntervalTask):
        raise TypeError("Task is not a time interval task. Inherit from TimeIntervalTask to mark it as such.")

    chunk: TimeChunk = task.interval  # type: ignore[attr-defined]

    start = _make_multiple(chunk.time_interval.start_time, chunk.chunk_size, before=True)
    end = _make_multiple(chunk.time_interval.end_time, chunk.chunk_size, before=False)

    n = (end - start) // chunk.chunk_size
    if n <= 1:  # we are already a leaf task
        return await call_next(context, TimeInterval(start, end))  # type: ignore[call-arg]

    chunks: list[datetime] = []
    if n < 4:  # we are a branch task with less than 4 sub chunks, so a further split is not worth it
        chunks = [start + chunk.chunk_size * i for i in range(n)] + [end]
    else:  # we have a large number of sub chunks, so let's split into 2 branches
        # in case we can't perfectly divide in the middle due to an uneven
        # number make the left half slightly larger than the right half
        middle = _make_multiple(start + (end - start) / 2, chunk.chunk_size, before=False)
        chunks = [start, middle, end]

    time_chunks = [
        TimeChunk(_TimeInterval(chunk_start, chunk_end), chunk.chunk_size)
        for chunk_start, chunk_end in pairwise(chunks)
    ]

    context.submit_batch(
        [replace(task, interval=time_chunk) for time_chunk in time_chunks]  # type: ignore[misc]
    )
    return None


@_time_interval_chunk
@dataclass_transform()
class SyncTimeIntervalTask(SyncTask):
    interval: TimeChunk

    @override
    def execute(self, context: ExecutionContext, time_interval: TimeInterval) -> None:  # type: ignore[override]
        pass


@_time_interval_chunk
@dataclass_transform()
class AsyncTimeIntervalTask(AsyncTask):
    interval: TimeChunk

    @override
    async def execute(self, context: ExecutionContext, time_interval: TimeInterval) -> None:  # type: ignore[override]
        pass


def batch_process_time_interval(interval: TimeIntervalLike, chunk_size: timedelta) -> TimeChunk:
    interval = TimeInterval.parse(interval).to_half_open()  # our time splitting assumes half open intervals
    return TimeChunk(_TimeInterval(interval.start, interval.end, False, False), chunk_size)


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
