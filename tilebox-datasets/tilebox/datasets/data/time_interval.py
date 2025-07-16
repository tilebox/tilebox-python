# kept for backwards compatibility, we can remove this whole file in the future

from warnings import warn

from tilebox.datasets.query.time_interval import (
    TimeInterval,
    TimeIntervalLike,
    datetime_to_timestamp,
    timestamp_to_datetime,
)

warn(
    "The time_interval module has been deprecated, import from tilebox.datasets.query instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["TimeInterval", "TimeIntervalLike", "datetime_to_timestamp", "timestamp_to_datetime"]
