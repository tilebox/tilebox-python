from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TypeAlias

import numpy as np
import xarray as xr
from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from pandas.core.tools.datetimes import DatetimeScalar, to_datetime

from tilebox.datasets.tilebox.v1 import query_pb2

_SMALLEST_POSSIBLE_TIMEDELTA = timedelta(microseconds=1)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# A type alias for the different types that can be used to specify a time interval
TimeIntervalLike: TypeAlias = (
    DatetimeScalar | tuple[DatetimeScalar, DatetimeScalar] | xr.DataArray | xr.Dataset | "TimeInterval"
)


@dataclass(frozen=True)
class TimeInterval:
    """
    A time interval from a given start to a given end time.
    Both the start and end time can be exclusive or inclusive.
    """

    start: datetime
    end: datetime

    # We use exclusive for start and inclusive for end, because that way when both are false
    # we have a half-open interval [start, end) which is the default behaviour we want to achieve.
    start_exclusive: bool = False
    end_inclusive: bool = False

    def __post_init__(self) -> None:
        """Validate the time interval"""
        if not isinstance(self.start, datetime):
            raise TypeError(f"Start time {self.start} must be a datetime object")
        if not isinstance(self.end, datetime):
            raise TypeError(f"End time {self.end} must be a datetime object")

        # in case datetime objects are timezone naive, we assume they are in UTC
        if self.start.tzinfo is None:
            object.__setattr__(self, "start", self.start.replace(tzinfo=timezone.utc))  # since self is frozen
        if self.end.tzinfo is None:
            object.__setattr__(self, "end", self.end.replace(tzinfo=timezone.utc))  # since self is frozen

    def to_half_open(self) -> "TimeInterval":
        """Convert the time interval to a half-open interval [start, end)"""
        return TimeInterval(
            start=self.start + int(self.start_exclusive) * _SMALLEST_POSSIBLE_TIMEDELTA,
            end=self.end + int(self.end_inclusive) * _SMALLEST_POSSIBLE_TIMEDELTA,
            start_exclusive=False,
            end_inclusive=False,
        )

    def astimezone(self, tzinfo: timezone) -> "TimeInterval":
        """Convert start and end time to the given timezone"""
        return TimeInterval(
            start=self.start.astimezone(tzinfo),
            end=self.end.astimezone(tzinfo),
            start_exclusive=self.start_exclusive,
            end_inclusive=self.end_inclusive,
        )

    def __eq__(self, other: object) -> bool:
        """Check whether two intervals are equal"""
        if not isinstance(other, TimeInterval):
            return False

        a, b = self.to_half_open(), other.to_half_open()
        return (a.start, a.end) == (b.start, b.end)

    def __hash__(self) -> int:
        """Hash the time interval"""

        # if two intervals are equal, they should have the same hash, so we convert to half-open intervals first
        half_open = self.to_half_open()
        return hash((half_open.start, half_open.end))

    def __repr__(self) -> str:
        return self.format()

    def format(self, endpoints: bool = True, sep: str = ", ", timespec: str = "milliseconds") -> str:
        """Human readable representation of the time interval

        Args:
            endpoints: Whether to format as interval using scientific interval notation [start, end].
                "[", "]" for closed intervals and "(", ")" for open intervals.
            sep: The separator to use between the start and end of the interval.
            timespec: Specifies the number of additional terms of the time to include. Valid options are 'auto',
                'hours', 'minutes', 'seconds', 'milliseconds' and 'microseconds'.
        """
        if self == _EMPTY_TIME_INTERVAL:
            return "<empty>"

        start = self.start.isoformat(timespec=timespec).replace("+00:00", " UTC")
        end = self.end.isoformat(timespec=timespec).replace("+00:00", " UTC")

        formatted = f"{start}{sep}{end}"
        if endpoints:
            start_ch = "[" if not self.start_exclusive else "("
            end_ch = "]" if self.end_inclusive else ")"
            formatted = f"{start_ch}{formatted}{end_ch}"
        return formatted

    def __str__(self) -> str:
        """Human readable representation of the time interval"""
        return self.format()

    @classmethod
    def parse(cls, arg: TimeIntervalLike) -> "TimeInterval":
        """
        Convert a variety of input types to a TimeInterval.

        Supported input types:
        - TimeInterval: Return the input as is
        - DatetimeScalar: Return a TimeInterval with start and end time set to the same value and the end time inclusive
        - tuple of two DatetimeScalar: Return a TimeInterval with start and end time
        - xr.DataArray: Return a TimeInterval with start and end time set to the first and last value in the array and
            the end time inclusive
        - xr.Dataset: Return a TimeInterval with start and end time set to the first and last value in the time
            coordinate of the dataset and the end time inclusive

        Args:
            arg: The input to convert

        Returns:
            TimeInterval: The parsed time interval
        """

        match arg:
            case TimeInterval(_, _, _, _):
                return arg
            case (start, end):
                return TimeInterval(start=_convert_to_datetime(start), end=_convert_to_datetime(end))
            case point_in_time if isinstance(point_in_time, DatetimeScalar | int):
                dt = _convert_to_datetime(point_in_time)
                return TimeInterval(start=dt, end=dt, start_exclusive=False, end_inclusive=True)
            case arr if (
                isinstance(arr, xr.DataArray)
                and arr.ndim == 1
                and arr.size > 0
                and arr.dtype == np.dtype("datetime64[ns]")
            ):
                start = arr.data[0]
                end = arr.data[-1]
                return TimeInterval(
                    start=_convert_to_datetime(start),
                    end=_convert_to_datetime(end),
                    start_exclusive=False,
                    end_inclusive=True,
                )
            case ds if isinstance(ds, xr.Dataset) and "time" in ds.coords:
                return cls.parse(ds.time)

        raise ValueError(f"Failed to convert {arg} ({type(arg)}) to TimeInterval)")

    @classmethod
    def from_message(
        cls, interval: query_pb2.TimeInterval
    ) -> "TimeInterval":  # lets use typing.Self once we require python >= 3.11
        """Convert a TimeInterval protobuf message to a TimeInterval object."""

        start = timestamp_to_datetime(interval.start_time)
        end = timestamp_to_datetime(interval.end_time)
        if start == _EPOCH and end == _EPOCH and not interval.start_exclusive and not interval.end_inclusive:
            return _EMPTY_TIME_INTERVAL

        return cls(
            start=timestamp_to_datetime(interval.start_time),
            end=timestamp_to_datetime(interval.end_time),
            start_exclusive=interval.start_exclusive,
            end_inclusive=interval.end_inclusive,
        )

    def to_message(self) -> query_pb2.TimeInterval:
        """Convert a TimeInterval object to a TimeInterval protobuf message."""
        return query_pb2.TimeInterval(
            start_time=datetime_to_timestamp(self.start),
            end_time=datetime_to_timestamp(self.end),
            start_exclusive=self.start_exclusive,
            end_inclusive=self.end_inclusive,
        )


# A sentinel value to use for time interval that are empty
_EMPTY_TIME_INTERVAL = TimeInterval(_EPOCH, _EPOCH, start_exclusive=True, end_inclusive=False)


def _convert_to_datetime(arg: DatetimeScalar) -> datetime:
    """Convert the given datetime scalar to a datetime object in the UTC timezone"""
    dt: datetime = to_datetime(arg, utc=True).to_pydatetime()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def timestamp_to_datetime(timestamp: Timestamp) -> datetime:
    """Convert a protobuf timestamp to a datetime object."""
    # datetime.fromtimestamp() expects a timestamp in seconds, not microseconds
    # if we pass it as a floating point number, we will run into rounding errors
    offset = timedelta(seconds=timestamp.seconds, microseconds=timestamp.nanos // 1000)
    return _EPOCH + offset


def datetime_to_timestamp(dt: datetime) -> Timestamp:
    """Convert a datetime object to a protobuf timestamp."""
    # manual epoch offset calculation to avoid rounding errors and support negative timestamps (before 1970)
    offset_us = datetime_to_us(dt.astimezone(timezone.utc))
    seconds, us = divmod(offset_us, 10**6)
    return Timestamp(seconds=seconds, nanos=us * 10**3)


def datetime_to_us(dt: datetime) -> int:
    """Convert a datetime object to a timestamp in microseconds since the epoch."""
    offset = dt - _EPOCH
    # implementation taken from timedelta.total_seconds() but without dividing by 10**6 at the end to avoid floating
    # point rounding errors
    return (offset.days * 86400 + offset.seconds) * 10**6 + offset.microseconds


def us_to_datetime(us: int) -> datetime:
    """Convert a timestamp in microseconds since the epoch to a datetime object."""
    return _EPOCH + timedelta(microseconds=us)


def timedelta_to_duration(td: timedelta) -> Duration:
    """Convert a timedelta to a duration protobuf message."""
    return Duration(seconds=int(td.total_seconds()), nanos=int(td.microseconds * 1000))


def duration_to_timedelta(duration: Duration) -> timedelta:
    """Convert a duration protobuf message to a timedelta."""
    return timedelta(seconds=duration.seconds, microseconds=duration.nanos // 1000)
