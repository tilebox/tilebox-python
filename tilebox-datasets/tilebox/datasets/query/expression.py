from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from math import isfinite
from typing import TYPE_CHECKING, ClassVar, NoReturn, TypeAlias

from protobuf.wkt.google.protobuf.duration_pb import Duration
from protobuf.wkt.google.protobuf.timestamp_pb import Timestamp

from tilebox.datasets.query.time_interval import datetime_to_timestamp, timedelta_to_duration
from tilebox.datasets.v1 import data_access_pb

if TYPE_CHECKING:
    import numpy as np

    _QueryScalar: TypeAlias = bool | int | float | str | bytes | datetime | timedelta | np.generic
else:
    _QueryScalar: TypeAlias = object

_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_UINT64_MAX = 2**64 - 1
_DURATION_MAX_SECONDS = 315_576_000_000


class Expression:
    """A server-side filter expression over queryable dataset fields.

    Expressions use SQL- and CQL2-compatible three-valued Boolean logic. A comparison with a missing or null field
    evaluates to unknown, and a datapoint matches only when the complete expression evaluates to true.
    """

    def __and__(self, other: "Expression") -> "Expression":
        return _combine(data_access_pb.LogicalOperator.AND, self, other)

    def __or__(self, other: "Expression") -> "Expression":
        return _combine(data_access_pb.LogicalOperator.OR, self, other)

    def __invert__(self) -> "Expression":
        return _Logical(data_access_pb.LogicalOperator.NOT, (self,))

    def __bool__(self) -> NoReturn:
        raise TypeError(
            "Query expressions cannot be evaluated as Python booleans. "
            "Use &, |, and ~; chained comparisons are unsupported."
        )

    def to_message(self) -> data_access_pb.FilterExpression:
        """Convert this expression to its protobuf representation."""
        # Each concrete expression node overrides this method with its protobuf representation.
        raise NotImplementedError

    @classmethod
    def from_message(cls, message: data_access_pb.FilterExpression) -> "Expression":  # noqa: C901
        """Construct an expression from its protobuf representation."""
        variants = [name for name in ("logical", "comparison", "is_null", "array_predicate") if message.has_field(name)]
        if len(variants) != 1:
            raise ValueError("A filter expression must contain exactly one expression node")

        variant = variants[0]
        if variant == "comparison":
            comparison = message.comparison
            assert comparison is not None
            if comparison.value is None:
                raise ValueError("A field comparison must contain a value")
            if comparison.operator not in _COMPARISON_OPERATORS:
                raise ValueError(f"Unknown field comparison operator: {comparison.operator}")
            query_value = _QueryValue.from_message(comparison.value)
            _validate_comparison(comparison.operator, query_value)
            return _Comparison(
                comparison.field_name,
                comparison.operator,
                query_value,
            )
        if variant == "is_null":
            assert message.is_null is not None
            return _NullCheck(message.is_null.field_name)
        if variant == "array_predicate":
            predicate = message.array_predicate
            assert predicate is not None
            return _ArrayPredicate(predicate.field_name, predicate.operator, tuple(predicate.values))

        logical = message.logical
        assert logical is not None
        if logical.operator not in _LOGICAL_OPERATORS:
            raise ValueError(f"Unknown logical operator: {logical.operator}")
        operands = tuple(cls.from_message(operand) for operand in logical.operands)
        if logical.operator == data_access_pb.LogicalOperator.NOT:
            if len(operands) != 1:
                raise ValueError("NOT requires exactly one operand")
        elif len(operands) < 2:
            raise ValueError("AND and OR require at least two operands")
        return _Logical(logical.operator, operands)


@dataclass(frozen=True, slots=True)
class Field:
    """A reference to a queryable dataset field."""

    __array_priority__: ClassVar[float] = 1000

    name: str

    __hash__ = None

    def __eq__(self, value: object) -> Expression:  # ty: ignore[invalid-method-override]
        return self._comparison(data_access_pb.FieldComparisonOperator.EQUAL, value)

    def __ne__(self, value: object) -> Expression:  # ty: ignore[invalid-method-override]
        return self._comparison(data_access_pb.FieldComparisonOperator.NOT_EQUAL, value)

    def __lt__(self, value: _QueryScalar) -> Expression:
        return self._comparison(data_access_pb.FieldComparisonOperator.LESS_THAN, value)

    def __le__(self, value: _QueryScalar) -> Expression:
        return self._comparison(data_access_pb.FieldComparisonOperator.LESS_THAN_OR_EQUAL, value)

    def __gt__(self, value: _QueryScalar) -> Expression:
        return self._comparison(data_access_pb.FieldComparisonOperator.GREATER_THAN, value)

    def __ge__(self, value: _QueryScalar) -> Expression:
        return self._comparison(data_access_pb.FieldComparisonOperator.GREATER_THAN_OR_EQUAL, value)

    def is_null(self) -> Expression:
        """Match datapoints where this field is missing or explicitly null."""
        return _NullCheck(self.name)

    def is_not_null(self) -> Expression:
        """Match datapoints where this field is present and non-null."""
        return ~self.is_null()

    def contains(self, value: str) -> Expression:
        """Match a queryable repeated enum containing this public value."""
        return self.contains_all([value])

    def contains_all(self, values: Iterable[str]) -> Expression:
        """Match a queryable repeated enum containing every value; an empty request matches all rows."""
        return self._array_predicate(data_access_pb.FieldArrayOperator.CONTAINS_ALL, values)

    def contains_any(self, values: Iterable[str]) -> Expression:
        """Match a queryable repeated enum containing any value; an empty request matches no rows."""
        return self._array_predicate(data_access_pb.FieldArrayOperator.OVERLAPS, values)

    def _array_predicate(self, operator: data_access_pb.FieldArrayOperator, values: Iterable[str]) -> Expression:
        if isinstance(values, str | bytes | Mapping) or not isinstance(values, Iterable):
            raise TypeError("Array predicates require an iterable of public strings, not a single string or mapping")
        return _ArrayPredicate(self.name, operator, tuple(values))

    def _comparison(self, operator: data_access_pb.FieldComparisonOperator, value: object) -> Expression:
        query_value = _QueryValue.parse(value)
        _validate_comparison(operator, query_value)
        return _Comparison(self.name, operator, query_value)


def field(name: str) -> Field:
    """Reference a queryable dataset field in a filter expression."""
    return Field(name)


@dataclass(frozen=True, slots=True)
class _QueryValue:
    kind: str
    value: bool | int | float | str | bytes | tuple[int, int]

    @classmethod
    def parse(cls, value: object) -> "_QueryValue":  # noqa: C901, PLR0911, PLR0912
        import numpy as np  # noqa: PLC0415

        if isinstance(value, Enum):
            raise TypeError("Enum query values must be public strings; use the member's string .value")
        if isinstance(value, bool | np.bool_):
            return cls("bool_value", bool(value))
        if isinstance(value, np.datetime64):
            if np.isnat(value):
                raise ValueError("NaT is not a valid query value")
            return cls("timestamp_value", _nanoseconds_to_parts(int(value.astype("datetime64[ns]").astype(np.int64))))
        if isinstance(value, np.timedelta64):
            if np.isnat(value):
                raise ValueError("NaT is not a valid query value")
            duration = Duration.from_nanos(int(value.astype("timedelta64[ns]").astype(np.int64)))
            _validate_duration(duration.seconds, duration.nanos)
            return cls("duration_value", (duration.seconds, duration.nanos))
        if isinstance(value, datetime):
            timestamp = datetime_to_timestamp(value)
            return cls("timestamp_value", (timestamp.seconds, timestamp.nanos))
        if isinstance(value, timedelta):
            duration = timedelta_to_duration(value)
            _validate_duration(duration.seconds, duration.nanos)
            return cls("duration_value", (duration.seconds, duration.nanos))
        if isinstance(value, np.unsignedinteger):
            integer = int(value)
            if integer > _UINT64_MAX:
                raise OverflowError("Unsigned query integer does not fit in uint64")
            return cls("uint64_value", integer)
        if isinstance(value, int | np.signedinteger):
            integer = int(value)
            if not _INT64_MIN <= integer <= _INT64_MAX:
                raise OverflowError("Query integer does not fit in int64")
            return cls("int64_value", integer)
        if isinstance(value, float | np.floating):
            number = float(value)
            if not isfinite(number):
                raise ValueError("Query float values must be finite")
            return cls("double_value", number)
        if isinstance(value, str | np.str_):
            return cls("string_value", str(value))
        if isinstance(value, bytes | np.bytes_):
            return cls("bytes_value", bytes(value))
        if value is None:
            raise TypeError("None is not a query value; use field(...).is_null()")
        raise TypeError(f"Unsupported query value type: {type(value).__name__}")

    @classmethod
    def from_message(cls, message: data_access_pb.FieldQueryValue) -> "_QueryValue":
        variants = [name for name in _QUERY_VALUE_KINDS if message.has_field(name)]
        if len(variants) != 1:
            raise ValueError("A field query value must contain exactly one typed literal")
        kind = variants[0]
        value = getattr(message, kind)
        if kind in {"timestamp_value", "duration_value"}:
            value = (value.seconds, value.nanos)
        if kind == "duration_value":
            _validate_duration(*value)
        return cls(kind, value)

    def to_message(self) -> data_access_pb.FieldQueryValue:
        if self.kind == "timestamp_value":
            if not isinstance(self.value, tuple):
                raise TypeError("Invalid timestamp query value")
            seconds, nanos = self.value
            return data_access_pb.FieldQueryValue(
                timestamp_value=Timestamp(seconds=seconds, nanos=nanos),
            )
        if self.kind == "duration_value":
            if not isinstance(self.value, tuple):
                raise TypeError("Invalid duration query value")
            seconds, nanos = self.value
            _validate_duration(seconds, nanos)
            return data_access_pb.FieldQueryValue(
                duration_value=Duration(seconds=seconds, nanos=nanos),
            )
        message = data_access_pb.FieldQueryValue()
        setattr(message, self.kind, self.value)
        return message


@dataclass(frozen=True, slots=True)
class _Comparison(Expression):
    field_name: str
    operator: data_access_pb.FieldComparisonOperator
    value: _QueryValue

    def to_message(self) -> data_access_pb.FilterExpression:
        return data_access_pb.FilterExpression(
            comparison=data_access_pb.FieldComparison(
                field_name=self.field_name,
                operator=self.operator,
                value=self.value.to_message(),
            )
        )


@dataclass(frozen=True, slots=True)
class _ArrayPredicate(Expression):
    field_name: str
    operator: data_access_pb.FieldArrayOperator
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.operator not in {
            data_access_pb.FieldArrayOperator.CONTAINS_ALL,
            data_access_pb.FieldArrayOperator.OVERLAPS,
        }:
            raise ValueError(f"Unknown array predicate operator: {self.operator}")
        if len(self.values) > 100:
            raise ValueError("Array predicates accept at most 100 values")
        for value in self.values:
            if not isinstance(value, str) or isinstance(value, Enum):
                raise TypeError("Array predicate values must be public strings")
            if not value:
                raise ValueError("Array predicate values must be nonempty strings")

    def to_message(self) -> data_access_pb.FilterExpression:
        return data_access_pb.FilterExpression(
            array_predicate=data_access_pb.FieldArrayPredicate(
                field_name=self.field_name,
                operator=self.operator,
                values=list(self.values),
            )
        )


@dataclass(frozen=True, slots=True)
class _NullCheck(Expression):
    field_name: str

    def to_message(self) -> data_access_pb.FilterExpression:
        return data_access_pb.FilterExpression(
            is_null=data_access_pb.FieldNullCheck(field_name=self.field_name),
        )


@dataclass(frozen=True, slots=True)
class _Logical(Expression):
    operator: data_access_pb.LogicalOperator
    operands: tuple[Expression, ...]

    def to_message(self) -> data_access_pb.FilterExpression:
        return data_access_pb.FilterExpression(
            logical=data_access_pb.LogicalExpression(
                operator=self.operator,
                operands=[operand.to_message() for operand in self.operands],
            )
        )


def _combine(operator: data_access_pb.LogicalOperator, left: Expression, right: Expression) -> Expression:
    if not isinstance(right, Expression):
        raise TypeError(f"Expected a query expression, got {type(right).__name__}")
    operands: tuple[Expression, ...] = ()
    for expression in (left, right):
        if isinstance(expression, _Logical) and expression.operator == operator:
            operands += expression.operands
        else:
            operands += (expression,)
    return _Logical(operator, operands)


def _nanoseconds_to_parts(nanoseconds: int) -> tuple[int, int]:
    return divmod(nanoseconds, 1_000_000_000)


def _validate_comparison(
    operator: data_access_pb.FieldComparisonOperator,
    value: _QueryValue,
) -> None:
    if value.kind == "bool_value" and operator not in {
        data_access_pb.FieldComparisonOperator.EQUAL,
        data_access_pb.FieldComparisonOperator.NOT_EQUAL,
    }:
        raise TypeError("Boolean query values only support == and !=")
    if value.kind == "double_value":
        if not isinstance(value.value, float):
            raise TypeError("Invalid double query value")
        if not isfinite(value.value):
            raise ValueError("Query float values must be finite")


def _validate_duration(seconds: int, nanos: int) -> None:
    if not -_DURATION_MAX_SECONDS <= seconds <= _DURATION_MAX_SECONDS:
        raise OverflowError("Query duration is outside the supported protobuf range")
    if not -999_999_999 <= nanos <= 999_999_999:
        raise ValueError("Query duration nanoseconds are outside the supported protobuf range")
    if seconds > 0 > nanos or seconds < 0 < nanos:
        raise ValueError("Query duration seconds and nanoseconds must have the same sign")


_COMPARISON_OPERATORS = {
    data_access_pb.FieldComparisonOperator.EQUAL,
    data_access_pb.FieldComparisonOperator.NOT_EQUAL,
    data_access_pb.FieldComparisonOperator.LESS_THAN,
    data_access_pb.FieldComparisonOperator.LESS_THAN_OR_EQUAL,
    data_access_pb.FieldComparisonOperator.GREATER_THAN,
    data_access_pb.FieldComparisonOperator.GREATER_THAN_OR_EQUAL,
}
_LOGICAL_OPERATORS = {
    data_access_pb.LogicalOperator.AND,
    data_access_pb.LogicalOperator.OR,
    data_access_pb.LogicalOperator.NOT,
}
_QUERY_VALUE_KINDS = (
    "bool_value",
    "int64_value",
    "uint64_value",
    "double_value",
    "string_value",
    "timestamp_value",
    "duration_value",
    "bytes_value",
)
