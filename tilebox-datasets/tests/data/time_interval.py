"""
Hypothesis strategies for generating random test data for tests.
"""

from datetime import datetime, timezone

import pandas as pd
from hypothesis.strategies import (
    DrawFn,
    booleans,
    composite,
    datetimes,
    just,
    sampled_from,
)
from pandas.core.tools.datetimes import DatetimeScalar

from tilebox.datasets.data.time_interval import (
    TimeInterval,
    datetime_to_us,
)

# The minimum and maximum datetime that can be represented by pandas.Timestamp and are therefore supported
# by the pd.to_datetime function which we are using for parsing datetime scalars.
_MIN_TIME_NANO_I64 = datetime(1677, 9, 22)
_MAX_TIME_NANO_I64 = datetime(2262, 4, 11)
# datetimes in a range that fit into a 64 bit signed integer when converted to a nanoseconds timestamp
i64_datetimes = datetimes(_MIN_TIME_NANO_I64, _MAX_TIME_NANO_I64, timezones=just(timezone.utc))


@composite
def time_intervals(draw: DrawFn, tzinfo: timezone | None = None) -> TimeInterval:
    """A hypothesis strategy for generating random time intervals"""
    datetime_strategy = datetimes(timezones=just(tzinfo)) if tzinfo is not None else datetimes()
    start = draw(datetime_strategy)
    end = draw(datetime_strategy)
    start, end = min(start, end), max(start, end)  # make sure start is before end
    start_exclusive = draw(booleans())
    end_inclusive = draw(booleans())
    return TimeInterval(start, end, start_exclusive, end_inclusive)


@composite
def datetime_scalars(draw: DrawFn) -> tuple[DatetimeScalar, datetime]:
    """A hypothesis strategy for generating random datetime scalars for utc datetimes which can be parsed by pandas."""
    dt = draw(i64_datetimes)
    scalar = draw(datetime_scalar_for_datetime(dt))
    return scalar, dt


@composite
def datetime_scalar_for_datetime(draw: DrawFn, dt: datetime) -> DatetimeScalar:
    """
    A hypothesis strategy for generating random datetime scalars for the given datetime.

    The datetime scalar is a representation of the given datetime in a format that can be parsed by pandas.to_datetime
    and is therefore understood by the tilebox.datasets.data._convert_to_datetime function, which is the backbone
    of the TimeInterval parsing functionality in the load() function of a dataset collection
    """
    understood_formats = [
        lambda dt: dt,  # converting a datetime to a datetime scalar should be a no-op
        lambda dt: pd.to_datetime(dt),  # pandas Timestamp objects are also supported
        lambda dt: pd.to_datetime(dt).to_datetime64(),  # and so are numpy datetime64 objects
        lambda dt: datetime_to_us(dt) * 10**3,  # timestamp in nanoseconds
        # as well as strings in various formats
        lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.%f"),
        lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.%f %Z"),
        lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S.%f"),
        lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S.%f %Z"),
    ]
    if dt.microsecond == 0:  # if the datetime has no microseconds we can also use formats without microseconds
        understood_formats += [
            lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S"),
            lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S %Z"),
            lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
            lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        ]
    if dt.microsecond == 0 and dt.second == 0 and dt.minute == 0 and dt.hour == 0:  # date formats without time
        understood_formats += [
            lambda dt: dt.strftime("%Y-%m-%d"),
        ]
    scalar_format = draw(sampled_from(understood_formats))
    return scalar_format(dt)
