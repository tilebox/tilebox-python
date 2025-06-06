from datetime import datetime, timezone

from hypothesis import given
from hypothesis.strategies import datetimes
from pandas.core.tools.datetimes import DatetimeScalar

from tests.data.time_interval import datetime_scalars, time_intervals
from tilebox.datasets.data.time_interval import (
    _SMALLEST_POSSIBLE_TIMEDELTA,
    TimeInterval,
    _convert_to_datetime,
    datetime_to_timestamp,
    timestamp_to_datetime,
)

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


@given(
    # we specify the min_value of the datetime to be min value + _SMALLEST_POSSIBLE_TIMEDELTA, so that we can
    # safely subtract the smallest possible timedelta from it still
    datetimes(min_value=datetime.min + _SMALLEST_POSSIBLE_TIMEDELTA),
    datetimes(min_value=datetime.min + _SMALLEST_POSSIBLE_TIMEDELTA),
)
def test_time_interval_eq_bounds_inclusive_exclusive(start: datetime, end: datetime) -> None:
    """Assert that different ways of specifying the same interval with different inclusivities are considered equal"""
    granularity = _SMALLEST_POSSIBLE_TIMEDELTA
    # a closed open interval [start, end)
    interval1 = TimeInterval(start, end, False, False)
    # is the same as a closed closed interval [start, end - 1ms]
    interval2 = TimeInterval(start, end - granularity, False, True)
    # and the same as a open open interval (start - 1ms, end)
    interval3 = TimeInterval(start - granularity, end, True, False)
    # and the same as a open closed interval (start - 1ms, end - 1ms]
    interval4 = TimeInterval(start - granularity, end - granularity, True, True)
    for interval in [interval1, interval2, interval3, interval4]:
        for other in [interval1, interval2, interval3, interval4]:
            assert interval == other


@given(time_intervals())
def test_time_interval_to_half_open_preserves_eq(interval: TimeInterval) -> None:
    """Assert that converting a time interval to a half-open interval preserves equality"""
    assert interval.to_half_open() == interval


@given(time_intervals())
def test_time_interval_repr(interval: TimeInterval) -> None:
    """Assert the repr of a time interval is as expected"""
    for r in (repr(interval), str(interval)):
        assert r.startswith("(") if interval.start_exclusive else r.startswith("[")
        assert r.endswith("]") if interval.end_inclusive else r.endswith(")")
        assert interval.start.strftime(_TIME_FORMAT) in r
        assert interval.end.strftime(_TIME_FORMAT) in r
        assert "UTC" in r


@given(time_intervals())
def test_time_interval_to_message_and_back(interval: TimeInterval) -> None:
    """Make sure converting an interval to a protobuf message and then back again ends up with the same interval."""
    # we always convert to UTC when converting to protobuf, so we loose the information of which timezone it was before
    assert TimeInterval.from_message(interval.to_message()) == interval.astimezone(timezone.utc)


@given(datetimes())
def test_datetime_to_timestamp_and_back(dt: datetime) -> None:
    """Make sure converting a datetime to a protobuf timestamp and then back again ends up with the same timestamp."""
    # we always convert to UTC when converting to protobuf, so we loose the information of which timezone it was before
    assert timestamp_to_datetime(datetime_to_timestamp(dt)) == dt.astimezone(timezone.utc)


@given(datetime_scalars())
def test_parse_datetime_scalar(values: tuple[DatetimeScalar, datetime]) -> None:
    """Make sure valid datetime scalar representations of a utc datetime object are parsed correctly"""
    scalar, dt = values
    assert _convert_to_datetime(scalar) == dt, f"Failed parsing datetime scalar {scalar}"


@given(datetime_scalars())
def test_parse_time_interval_from_scalar(values: tuple[DatetimeScalar, datetime]) -> None:
    """Make sure valid parsing a single datetime scalar results in a time interval with start and end set to the same"""
    scalar, dt = values
    interval = TimeInterval.parse(scalar)
    assert interval.start == dt, f"Failed parsing interval from scalar {scalar}"
    assert interval.end == dt, f"Failed parsing interval from scalar {scalar}"
    assert not interval.start_exclusive
    assert interval.end_inclusive


@given(datetime_scalars(), datetime_scalars())
def test_parse_time_interval_from_tuple(
    start: tuple[DatetimeScalar, datetime], end: tuple[DatetimeScalar, datetime]
) -> None:
    """Make sure valid parsing a single datetime scalar results in a time interval with start and end set to the same"""
    start_scalar, start_dt = start
    end_scalar, end_dt = end
    if end_dt < start_dt:
        start_scalar, end_scalar = end_scalar, start_scalar
        start_dt, end_dt = end_dt, start_dt

    interval = TimeInterval.parse((start_scalar, end_scalar))
    assert interval.start == start_dt, f"Failed parsing interval for ({start_scalar}, {end_scalar})"
    assert interval.end == end_dt, f"Failed parsing interval for ({start_scalar}, {end_scalar})"
    assert not interval.start_exclusive
    assert not interval.end_inclusive
