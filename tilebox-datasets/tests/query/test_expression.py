from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum

import numpy as np
import pytest

from tilebox.datasets.datasets.v1 import data_access_pb2
from tilebox.datasets.query import Expression, field


class Quality(Enum):
    GOOD = "good"


class NumericQuality(IntEnum):
    GOOD = 1


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        (False, "bool_value", False),
        (0, "int64_value", 0),
        (np.uint64(2**63), "uint64_value", 2**63),
        (0.0, "double_value", 0.0),
        ("", "string_value", ""),
        (b"", "bytes_value", b""),
        (Quality.GOOD, "enum_name", "GOOD"),
        (NumericQuality.GOOD, "enum_name", "GOOD"),
    ],
)
def test_query_value_types(value: object, kind: str, expected: object) -> None:
    message = (field("quality") == value).to_message().comparison.value
    assert message.HasField(kind)
    assert getattr(message, kind) == expected


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 7, 27, 12, 30, tzinfo=timezone.utc),
        timedelta(days=-1, microseconds=123),
        np.datetime64("2026-07-27T12:30:00.123456789"),
        np.timedelta64(-123456789, "ns"),
    ],
)
def test_well_known_query_values_round_trip(value: object) -> None:
    expression = field("value") == value
    assert Expression.from_message(expression.to_message()) == expression


@pytest.mark.parametrize(
    ("value", "seconds", "nanos"),
    [
        (timedelta(microseconds=-1), 0, -1000),
        (np.timedelta64(-123456789, "ns"), 0, -123456789),
        (timedelta(seconds=-1, microseconds=-1), -1, -1000),
    ],
)
def test_negative_duration_values(value: object, seconds: int, nanos: int) -> None:
    duration = (field("value") == value).to_message().comparison.value.duration_value
    assert (duration.seconds, duration.nanos) == (seconds, nanos)


@pytest.mark.parametrize(
    "value",
    [
        np.bool_(True),
        np.int64(3),
        np.uint64(2**63),
        np.float64(3.5),
        np.datetime64("2026-07-27T12:30:00.123456789"),
        np.timedelta64(-123456789, "ns"),
    ],
)
def test_numpy_query_values_preserve_type_when_reflected(value: object) -> None:
    field_first = (field("value") == value).to_message().comparison.value
    value_first = (value == field("value")).to_message().comparison.value
    assert value_first == field_first


def test_logical_expression_shape_and_round_trip() -> None:
    expression = (
        (field("cloud_cover") < 20)
        & (field("quality") >= 80)
        & ((field("platform") == "sentinel-2") | field("platform").is_null())
        & field("title").is_not_null()
    )

    message = expression.to_message()
    assert message.logical.operator == data_access_pb2.LOGICAL_OPERATOR_AND
    assert len(message.logical.operands) == 4
    assert message.logical.operands[2].logical.operator == data_access_pb2.LOGICAL_OPERATOR_OR
    assert message.logical.operands[3].logical.operator == data_access_pb2.LOGICAL_OPERATOR_NOT
    assert Expression.from_message(message) == expression


def test_query_expression_cannot_be_used_as_boolean() -> None:
    expression = field("quality") == 1
    with pytest.raises(TypeError, match=r"Use &, \|, and ~"):
        bool(expression)

    with pytest.raises(TypeError, match="chained comparisons"):
        _ = 0 < field("quality") < 10


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), [], object()])
def test_invalid_query_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _ = field("quality") == value


def test_query_duration_rejects_values_outside_protobuf_range() -> None:
    with pytest.raises(OverflowError, match="outside the supported protobuf range"):
        _ = field("duration") == timedelta.max


def test_invalid_query_operators() -> None:
    with pytest.raises(TypeError, match="Boolean query values only support"):
        _ = field("enabled") < True

    with pytest.raises(TypeError, match="Expected a query expression"):
        (field("quality") == 1) & 2  # type: ignore[operator]


def test_invalid_expression_message() -> None:
    with pytest.raises(ValueError, match="exactly one expression node"):
        Expression.from_message(data_access_pb2.FilterExpression())

    malformed_not = data_access_pb2.FilterExpression(
        logical=data_access_pb2.LogicalExpression(operator=data_access_pb2.LOGICAL_OPERATOR_NOT)
    )
    with pytest.raises(ValueError, match="NOT requires exactly one operand"):
        Expression.from_message(malformed_not)


@pytest.mark.parametrize(
    "message",
    [
        data_access_pb2.FilterExpression(
            comparison=data_access_pb2.FieldComparison(
                field_name="quality",
                operator=data_access_pb2.FIELD_COMPARISON_OPERATOR_LESS_THAN,
                value=data_access_pb2.FieldQueryValue(bool_value=True),
            )
        ),
        data_access_pb2.FilterExpression(
            comparison=data_access_pb2.FieldComparison(
                field_name="quality",
                operator=data_access_pb2.FIELD_COMPARISON_OPERATOR_EQUAL,
                value=data_access_pb2.FieldQueryValue(double_value=float("nan")),
            )
        ),
    ],
)
def test_expression_message_cannot_bypass_comparison_validation(
    message: data_access_pb2.FilterExpression,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        Expression.from_message(message)
