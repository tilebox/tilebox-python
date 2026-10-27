"""Compatibility imports for shared time intervals and timestamp conversions."""

from _tilebox.time import (
    _convert_to_datetime,
    datetime_to_timestamp,
    datetime_to_us,
    duration_to_timedelta,
    timedelta_to_duration,
    timestamp_to_datetime,
    us_to_datetime,
)
from tilebox.query.time_interval import (
    _EMPTY_TIME_INTERVAL,
    _SMALLEST_POSSIBLE_TIMEDELTA,
    TimeInterval,
    TimeIntervalLike,
)

__all__ = [
    "_EMPTY_TIME_INTERVAL",
    "_SMALLEST_POSSIBLE_TIMEDELTA",
    "TimeInterval",
    "TimeIntervalLike",
    "_convert_to_datetime",
    "datetime_to_timestamp",
    "datetime_to_us",
    "duration_to_timedelta",
    "timedelta_to_duration",
    "timestamp_to_datetime",
    "us_to_datetime",
]
