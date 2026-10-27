"""Internal datetime and protobuf conversions."""

from datetime import UTC, datetime, timedelta
from typing import Any

from protobuf.wkt.google.protobuf.duration_pb import Duration
from protobuf.wkt.google.protobuf.timestamp_pb import Timestamp

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _convert_to_datetime(arg: Any) -> datetime:
    """Convert a datetime scalar to UTC, loading pandas only for non-native values."""
    # pandas.Timestamp subclasses datetime; retain its existing conversion and precision behavior.
    if type(arg) is datetime:
        return arg.replace(tzinfo=UTC) if arg.tzinfo is None else arg.astimezone(UTC)

    try:
        from pandas.core.tools.datetimes import to_datetime  # noqa: PLC0415
    except ModuleNotFoundError as error:
        if error.name != "pandas":
            raise
        raise ImportError(
            "Parsing strings and scientific datetime values requires pandas. "
            "Install pandas or pass Python datetime objects."
        ) from error

    dt: datetime = to_datetime(arg, utc=True).to_pydatetime()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def timestamp_to_datetime(timestamp: Timestamp | None) -> datetime:
    """Convert a protobuf timestamp without floating-point rounding."""
    if timestamp is None:
        return _EPOCH
    return _EPOCH + timedelta(seconds=timestamp.seconds, microseconds=timestamp.nanos // 1000)


def datetime_to_timestamp(dt: datetime) -> Timestamp:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    seconds, us = divmod(datetime_to_us(dt.astimezone(UTC)), 10**6)
    return Timestamp(seconds=seconds, nanos=us * 10**3)


def datetime_to_us(dt: datetime) -> int:
    offset = dt - _EPOCH
    return (offset.days * 86400 + offset.seconds) * 10**6 + offset.microseconds


def us_to_datetime(us: int) -> datetime:
    return _EPOCH + timedelta(microseconds=us)


def timedelta_to_duration(td: timedelta) -> Duration:
    return Duration.from_nanos(((td.days * 86400 + td.seconds) * 10**6 + td.microseconds) * 1000)


def duration_to_timedelta(duration: Duration) -> timedelta:
    return timedelta(seconds=duration.seconds, microseconds=duration.nanos // 1000)
