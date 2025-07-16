from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from tilebox.datasets.datasets.v1 import timeseries_pb2
from tilebox.datasets.query.id_interval import IDInterval
from tilebox.datasets.query.time_interval import TimeInterval, duration_to_timedelta, timedelta_to_duration
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message


@dataclass
class TimeseriesDatasetChunk:
    dataset_id: UUID
    collection_id: UUID
    time_interval: TimeInterval | None
    datapoint_interval: IDInterval | None
    branch_factor: int
    chunk_size: int
    datapoints_per_365_days: int

    @classmethod
    def from_message(cls, chunk: timeseries_pb2.TimeseriesDatasetChunk) -> "TimeseriesDatasetChunk":
        datapoint_interval = None
        if (
            chunk.datapoint_interval
            and chunk.datapoint_interval.start_id
            and chunk.datapoint_interval.end_id
            and chunk.datapoint_interval.start_id.uuid
            and chunk.datapoint_interval.end_id.uuid
        ):
            datapoint_interval = IDInterval.from_message(chunk.datapoint_interval)

        time_interval = None
        if chunk.time_interval and chunk.time_interval.start_time and chunk.time_interval.end_time:
            time_interval = TimeInterval.from_message(chunk.time_interval)

        return cls(
            dataset_id=uuid_message_to_uuid(chunk.dataset_id),
            collection_id=uuid_message_to_uuid(chunk.collection_id),
            time_interval=time_interval,
            datapoint_interval=datapoint_interval,
            branch_factor=chunk.branch_factor,
            chunk_size=chunk.chunk_size,
            datapoints_per_365_days=chunk.datapoints_per_365_days,
        )

    def to_message(self) -> timeseries_pb2.TimeseriesDatasetChunk:
        return timeseries_pb2.TimeseriesDatasetChunk(
            dataset_id=uuid_to_uuid_message(self.dataset_id),
            collection_id=uuid_to_uuid_message(self.collection_id),
            time_interval=self.time_interval.to_message() if self.time_interval else None,
            datapoint_interval=self.datapoint_interval.to_message() if self.datapoint_interval else None,
            branch_factor=self.branch_factor,
            chunk_size=self.chunk_size,
            datapoints_per_365_days=self.datapoints_per_365_days,
        )

    # needed to serialize as protobuf in tasks
    def SerializeToString(self) -> bytes:  # noqa: N802
        return self.to_message().SerializeToString()

    @classmethod
    def FromString(cls, s: bytes) -> "TimeseriesDatasetChunk":  # noqa: N802
        return TimeseriesDatasetChunk.from_message(timeseries_pb2.TimeseriesDatasetChunk.FromString(s))


@dataclass
class TimeChunk:
    time_interval: TimeInterval
    chunk_size: timedelta

    @classmethod
    def from_message(cls, chunk: timeseries_pb2.TimeChunk) -> "TimeChunk":
        return cls(
            time_interval=TimeInterval.from_message(chunk.time_interval),
            chunk_size=duration_to_timedelta(chunk.chunk_size),
        )

    def to_message(self) -> timeseries_pb2.TimeChunk:
        return timeseries_pb2.TimeChunk(
            time_interval=self.time_interval.to_message(),
            chunk_size=timedelta_to_duration(self.chunk_size),
        )

    # needed to serialize as protobuf in tasks
    def SerializeToString(self) -> bytes:  # noqa: N802
        return self.to_message().SerializeToString()

    @classmethod
    def FromString(cls, s: bytes) -> "TimeChunk":  # noqa: N802
        return TimeChunk.from_message(timeseries_pb2.TimeChunk.FromString(s))
