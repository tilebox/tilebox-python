from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from tilebox.datasets.query.id_interval import IDInterval
from tilebox.datasets.query.time_interval import TimeInterval, duration_to_timedelta, timedelta_to_duration
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.datasets.v1 import timeseries_pb


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
    def from_message(cls, chunk: timeseries_pb.TimeseriesDatasetChunk) -> "TimeseriesDatasetChunk":
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
        if (
            chunk.time_interval is not None
            and chunk.time_interval.start_time is not None
            and chunk.time_interval.end_time is not None
        ):
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

    def to_message(self) -> timeseries_pb.TimeseriesDatasetChunk:
        return timeseries_pb.TimeseriesDatasetChunk(
            dataset_id=uuid_to_uuid_message(self.dataset_id),
            collection_id=uuid_to_uuid_message(self.collection_id),
            time_interval=self.time_interval.to_message() if self.time_interval else None,
            datapoint_interval=self.datapoint_interval.to_message() if self.datapoint_interval else None,
            branch_factor=self.branch_factor,
            chunk_size=self.chunk_size,
            datapoints_per_365_days=self.datapoints_per_365_days,
        )

    def to_binary(self) -> bytes:
        """Serialize the chunk in native protobuf wire format."""
        return self.to_message().to_binary()

    @classmethod
    def from_binary(cls, s: bytes) -> "TimeseriesDatasetChunk":
        """Parse a chunk from native protobuf wire format."""
        return TimeseriesDatasetChunk.from_message(timeseries_pb.TimeseriesDatasetChunk.from_binary(s))


@dataclass
class TimeChunk:
    time_interval: TimeInterval
    chunk_size: timedelta

    @classmethod
    def from_message(cls, chunk: timeseries_pb.TimeChunk) -> "TimeChunk":
        if chunk.time_interval is None or chunk.chunk_size is None:
            raise ValueError("Time chunk requires a time interval and chunk size")
        return cls(
            time_interval=TimeInterval.from_message(chunk.time_interval),
            chunk_size=duration_to_timedelta(chunk.chunk_size),
        )

    def to_message(self) -> timeseries_pb.TimeChunk:
        return timeseries_pb.TimeChunk(
            time_interval=self.time_interval.to_message(),
            chunk_size=timedelta_to_duration(self.chunk_size),
        )

    def to_binary(self) -> bytes:
        """Serialize the chunk in native protobuf wire format."""
        return self.to_message().to_binary()

    @classmethod
    def from_binary(cls, s: bytes) -> "TimeChunk":
        """Parse a chunk from native protobuf wire format."""
        return TimeChunk.from_message(timeseries_pb.TimeChunk.from_binary(s))
