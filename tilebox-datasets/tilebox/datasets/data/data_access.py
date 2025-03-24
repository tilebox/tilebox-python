from dataclasses import dataclass

from tilebox.datasets.data.datapoint import DatapointInterval
from tilebox.datasets.data.time_interval import TimeInterval
from tilebox.datasets.datasetsv1 import data_access_pb2


@dataclass(frozen=True)
class QueryFilters:
    temporal_interval: TimeInterval | DatapointInterval

    @classmethod
    def from_message(cls, filters: data_access_pb2.QueryFilters) -> "QueryFilters":
        if filters.HasField("time_interval"):
            return cls(temporal_interval=TimeInterval.from_message(filters.time_interval))
        if filters.HasField("datapoint_interval"):
            return cls(temporal_interval=DatapointInterval.from_message(filters.datapoint_interval))
        raise ValueError("Invalid filter: time or datapoint interval must be set")

    def to_message(self) -> data_access_pb2.QueryFilters:
        if isinstance(self.temporal_interval, TimeInterval):
            return data_access_pb2.QueryFilters(time_interval=self.temporal_interval.to_message())

        return data_access_pb2.QueryFilters(datapoint_interval=self.temporal_interval.to_message())
