import re
from collections.abc import Sequence
from datetime import timedelta
from enum import Enum
from functools import lru_cache
from typing import Any, TypeGuard, TypeVar
from uuid import UUID

import numpy as np
import pandas as pd
from numpy import dtypes as npdtypes
from pandas.core.tools.datetimes import DatetimeScalar, to_datetime
from pandas.core.tools.timedeltas import to_timedelta
from protobuf import (
    DescEnum,
    DescField,
    DescFieldValueEnum,
    DescFieldValueList,
    DescFieldValueMessage,
    DescFieldValueScalar,
    DescMessage,
    Message,
    ScalarType,
)
from protobuf.wkt.google.protobuf.duration_pb import Duration
from protobuf.wkt.google.protobuf.timestamp_pb import Timestamp
from shapely import from_wkb

from tilebox.datasets.data.datasets import AnnotatedType
from tilebox.datasets.schema import _MESSAGE_FIELD_TYPES, Assets
from tilebox.datasets.v1.well_known_types_pb import UUID as UUIDMessage  # noqa: N811
from tilebox.datasets.v1.well_known_types_pb import Geometry, LatLon, LatLonAlt, Quaternion, Vec3

ScalarProtoFieldValue = Message | float | str | bool | bytes
_MessageT = TypeVar("_MessageT", bound=Message)


ProtoFieldValue = ScalarProtoFieldValue | Sequence[ScalarProtoFieldValue] | None

_FILL_VALUES_BY_DTYPE: dict[type[np.dtype[Any]], Any] = {
    npdtypes.Int8DType: np.int8(0),
    npdtypes.Int16DType: np.int16(0),
    npdtypes.Int32DType: np.int32(0),
    npdtypes.Int64DType: np.int64(0),
    npdtypes.UInt8DType: np.uint8(0),
    npdtypes.UInt16DType: np.uint16(0),
    npdtypes.UInt32DType: np.uint32(0),
    npdtypes.UInt64DType: np.uint64(0),
    npdtypes.Float16DType: np.float16(np.nan),
    npdtypes.Float32DType: np.float32(np.nan),
    npdtypes.Float64DType: np.float64(np.nan),
    npdtypes.Complex64DType: np.complex64(np.nan),
    npdtypes.Complex128DType: np.complex128(np.nan),
    npdtypes.BoolDType: False,
    npdtypes.StrDType: "",
    npdtypes.ObjectDType: None,
    npdtypes.DateTime64DType: np.datetime64("NaT", "ns"),
    npdtypes.TimeDelta64DType: np.timedelta64("NaT", "ns"),
}


def _to_dtype_and_fill_value(
    dtype: type | str | np.dtype,
) -> tuple[np.dtype, str | int | np.datetime64 | np.timedelta64 | bool | None]:
    npdtype = np.dtype(dtype)
    fill_avlue = _FILL_VALUES_BY_DTYPE.get(type(npdtype), 0)
    return npdtype, fill_avlue


class ProtobufFieldType:
    def __init__(
        self, dtype: type | str | np.dtype, value_dim: int = 1, value_dim_meta: tuple[str, list[str]] | None = None
    ) -> None:
        self.dtype, self.fill_value = _to_dtype_and_fill_value(dtype)
        self.value_dim = value_dim
        self.value_dim_meta = value_dim_meta

    def from_proto(self, value: ProtoFieldValue) -> Any:
        return value

    def to_proto(self, value: Any) -> ProtoFieldValue | None:
        return value


class MessageField(ProtobufFieldType):
    """Normalize dynamically loaded values into public native message classes."""

    def __init__(
        self,
        value_type: type[Message],
        *,
        read_type: type[Message] | None = None,
    ) -> None:
        """Initialize the public message class used for conversion."""
        super().__init__(object)
        self._value_type = value_type
        self._read_type = read_type or value_type

    def from_proto(self, value: ProtoFieldValue) -> Message:
        if not isinstance(value, Message) or value.desc().type_name != self._value_type.desc().type_name:
            raise TypeError(f"Expected {self._value_type.__name__} message but got {type(value)}")
        return self._read_type.from_binary(value.to_binary())

    def to_proto(self, value: Message) -> Message | None:
        if is_missing(value):
            return None
        if not isinstance(value, self._value_type):
            raise TypeError(f"Expected {self._value_type.__name__} message but got {type(value)}")
        return self._value_type.from_binary(value.to_binary())


class BoolField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(bool)

    def from_proto(self, value: ProtoFieldValue) -> bool:
        return bool(value)

    def to_proto(self, value: Any) -> bool:
        # the protobuf constructor only works with the builtin bool, not with np.False_ or similar
        # therefore we need a special field type for it to make sure it is always converted
        # avoids DeprecationWarning: In future, it will be an error for 'np.bool' scalars to be interpreted as an index
        return bool(value)


class EnumField(ProtobufFieldType):
    def __init__(self, name_lookup: dict[int, str]) -> None:
        super().__init__(object)
        self._values_to_name = name_lookup
        self._names_to_value = {name: value for value, name in name_lookup.items()}

    def from_proto(self, value: ProtoFieldValue) -> str:
        if not isinstance(value, int):
            raise TypeError(f"Expected int message but got {type(value)}")
        try:
            return self._values_to_name[value]
        except KeyError as error:
            raise ValueError(f"Invalid enum value {value}") from error

    def to_proto(self, value: str | int | Enum) -> int:
        if isinstance(value, Enum):
            value = value.name
        if isinstance(value, (str, np.str_)):
            try:
                return self._names_to_value[value]
            except KeyError as error:
                raise ValueError(f"Invalid enum name {value!r}") from error
        integer_value = int(value)
        if integer_value not in self._values_to_name:
            raise ValueError(f"Invalid enum value {value}")  # during ingestion, we can raise an error here
        return integer_value


class PublicEnumField(EnumField):
    """Convert custom enum values without exposing protobuf symbols or numbers."""

    def to_proto(self, value: Any) -> int:
        if not isinstance(value, str):
            raise TypeError("Custom enum values must be public strings")
        try:
            return self._names_to_value[value]
        except KeyError as error:
            raise ValueError(f"Unknown public enum value {value!r}") from error


def enum_field_types(schema: AnnotatedType, message_type: type[Message]) -> dict[str, ProtobufFieldType]:
    """Build dataset-local converters; annotations are not part of the message-class cache."""
    if not any(annotation.enum_values for annotation in schema.field_annotations):
        return {}
    descriptor = message_type.desc()
    # Native descriptor collections may use numeric order. The wire contract uses declaration order.
    fields = descriptor.proto.field
    if len(fields) != len(schema.field_annotations):
        raise ValueError("Custom enum schema requires one annotation per field, including empty annotations")
    fields_by_name = {field.name: field for field in descriptor.fields}
    result: dict[str, ProtobufFieldType] = {}
    for field, annotation in zip(fields, schema.field_annotations, strict=True):
        if not annotation.enum_values:
            continue
        value = fields_by_name[field.name].value
        enum = (
            value.element
            if isinstance(value, DescFieldValueList)
            else value.enum
            if isinstance(value, DescFieldValueEnum)
            else None
        )
        if not isinstance(enum, DescEnum):
            raise TypeError(f"Field {field.name!r}: enum_values requires an enum field")
        members = [member for member in enum.proto.value if member.number != 0]
        public_values = annotation.enum_values
        if (
            len(members) != len(public_values)
            or any(not name for name in public_values)
            or len(set(public_values)) != len(public_values)
            or len({member.number for member in members}) != len(members)
        ):
            raise ValueError(f"Field {field.name!r}: invalid enum_values mapping")
        result[field.name] = PublicEnumField(
            {member.number: name for member, name in zip(members, public_values, strict=True)}
        )
    return result


class TimestampField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__("datetime64[ns]")

    def from_proto(self, value: ProtoFieldValue) -> int:
        if not _is_message(value, Timestamp):
            raise TypeError(f"Expected Timestamp message but got {type(value)}")
        return value.to_nanos()

    def to_proto(self, value: DatetimeScalar) -> Timestamp | None:
        if is_missing(value) or (isinstance(value, np.datetime64) and np.isnat(value)):
            return None
        # we use pandas to_datetime function to handle a variety of input types that can be coerced to datetimes
        return Timestamp.from_nanos(int(to_datetime(value, utc=True).as_unit("ns").value))


class TimeDeltaField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__("timedelta64[ns]")

    def from_proto(self, value: ProtoFieldValue) -> int:
        if not _is_message(value, Duration):
            raise TypeError(f"Expected Duration message but got {type(value)}")
        return value.seconds * 10**9 + value.nanos

    def to_proto(self, value: str | float | timedelta | np.timedelta64) -> Duration | None:
        if is_missing(value) or (isinstance(value, np.timedelta64) and np.isnat(value)):
            return None
        # we use pandas to_timedelta function to handle a variety of input types that can be coerced to timedeltas
        # pandas accepts np.timedelta64 at runtime, but its overloads omit it.
        return Duration.from_nanos(int(to_timedelta(value).as_unit("ns").value))  # ty: ignore[no-matching-overload]


class UUIDField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__("<U36")

    def from_proto(self, value: ProtoFieldValue) -> str:
        if not _is_message(value, UUIDMessage):
            raise TypeError(f"Expected UUID message but got {type(value)}")
        return str(UUID(bytes=value.uuid))

    def to_proto(self, value: str | UUID) -> UUIDMessage | None:
        if is_missing(value) or value == "":  # missing or empty string
            return None

        if isinstance(value, str):
            value = UUID(value)

        return UUIDMessage(uuid=value.bytes)


class GeometryField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(object)

    def from_proto(self, value: ProtoFieldValue) -> Any:
        if not _is_message(value, Geometry):
            raise TypeError(f"Expected Geometry message but got {type(value)}")
        return from_wkb(value.wkb)

    def to_proto(self, value: Any) -> Geometry | None:
        if is_missing(value):
            return None
        return Geometry(wkb=value.wkb)


class Vec3Field(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=3, value_dim_meta=("vec3", ["x", "y", "z"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float, float]:
        if not _is_message(value, Vec3):
            raise TypeError(f"Expected Vec3 message but got {type(value)}")
        return value.x, value.y, value.z

    def to_proto(self, value: tuple[float, float, float]) -> Vec3 | None:
        if is_missing(value) or np.all(np.isnan(value)):
            return None
        return Vec3(x=value[0], y=value[1], z=value[2])


class QuaternionField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=4, value_dim_meta=("quaternion", ["q1", "q2", "q3", "q4"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float, float, float]:
        if not _is_message(value, Quaternion):
            raise TypeError(f"Expected Quaternion message but got {type(value)}")
        return value.q1, value.q2, value.q3, value.q4

    def to_proto(self, value: tuple[float, float, float, float]) -> Quaternion | None:
        if is_missing(value) or np.all(np.isnan(value)):
            return None
        return Quaternion(q1=value[0], q2=value[1], q3=value[2], q4=value[3])


class LatLonField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=2, value_dim_meta=("latlon", ["latitude", "longitude"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float]:
        if not _is_message(value, LatLon):
            raise TypeError(f"Expected LatLon message but got {type(value)}")
        return value.latitude, value.longitude

    def to_proto(self, value: tuple[float, float]) -> LatLon | None:
        if is_missing(value) or np.all(np.isnan(value)):
            return None
        return LatLon(latitude=value[0], longitude=value[1])


class LatLonAltField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=3, value_dim_meta=("lat_lon_alt", ["latitude", "longitude", "altitude"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float, float]:
        if not _is_message(value, LatLonAlt):
            raise TypeError(f"Expected LatLonAlt message but got {type(value)}")

        return value.latitude, value.longitude, value.altitude

    def to_proto(self, value: tuple[float, float, float]) -> LatLonAlt | None:
        if is_missing(value) or np.all(np.isnan(value)):
            return None
        return LatLonAlt(latitude=value[0], longitude=value[1], altitude=value[2])


# A mapping from protobuf field types to the corresponding numpy data types
_PROTOBUF_TYPE_TO_NUMPY_TYPE = {
    ScalarType.DOUBLE: float,
    ScalarType.FLOAT: np.float32,
    ScalarType.INT64: np.int64,
    ScalarType.SINT64: np.int64,
    ScalarType.SFIXED64: np.int64,
    ScalarType.UINT64: np.uint64,
    ScalarType.FIXED64: np.uint64,
    ScalarType.INT32: np.int32,
    ScalarType.SINT32: np.int32,
    ScalarType.SFIXED32: np.int32,
    ScalarType.UINT32: np.uint32,
    ScalarType.FIXED32: np.uint32,
    ScalarType.STRING: object,
    ScalarType.BYTES: object,
}


class _AssetsDisplay(Assets):
    """Assets value with concise text representations, including in xarray displays."""

    def __repr__(self) -> str:
        return f"[{', '.join(a.key for a in self.assets)}]"

    def __str__(self) -> str:
        return f"{len(self.assets)} assets"


_MESSAGE_NAMES_TO_FIELDS: dict[str, ProtobufFieldType] = {
    "google.protobuf.Timestamp": TimestampField(),
    "google.protobuf.Duration": TimeDeltaField(),
    **{
        value_type.desc().type_name: MessageField(
            value_type,
            read_type=_AssetsDisplay if value_type is Assets else None,
        )
        for value_type in _MESSAGE_FIELD_TYPES
    },
    "datasets.v1.UUID": UUIDField(),
    "datasets.v1.Geometry": GeometryField(),
    "datasets.v1.Vec3": Vec3Field(),
    "datasets.v1.Quaternion": QuaternionField(),
    "datasets.v1.LatLon": LatLonField(),
    "datasets.v1.LatLonAlt": LatLonAltField(),
}


def _is_message(value: object, message_type: type[_MessageT]) -> TypeGuard[_MessageT]:
    return isinstance(value, Message) and value.desc().type_name == message_type.desc().type_name


@lru_cache(maxsize=4096)
def infer_field_type(field: DescField) -> ProtobufFieldType:
    """Cache scientific field conversion by native descriptor identity."""
    match field.value:
        case DescFieldValueMessage(message=message):
            element = message
        case DescFieldValueEnum(enum=enum):
            element = enum
        case DescFieldValueScalar(scalar=scalar):
            element = scalar
        case DescFieldValueList(element=element):
            pass
        case _:
            raise ValueError(f"Unsupported field: {field.name}")
    if isinstance(element, DescMessage):
        return _MESSAGE_NAMES_TO_FIELDS.get(element.type_name, ProtobufFieldType(object))
    if isinstance(element, DescEnum):
        return EnumField(_enum_mapping(element))
    if element == ScalarType.BOOL:
        return BoolField()
    return ProtobufFieldType(_PROTOBUF_TYPE_TO_NUMPY_TYPE[element])


def enum_mapping_from_field_descriptor(field: DescField) -> dict[int, str]:
    """Create a mapping from enum values to their names.

    Args:
        field: The field descriptor to create the mapping for. Must be of type FieldDescriptor.TYPE_ENUM.
    """
    value = field.value
    enum = (
        value.element
        if isinstance(value, DescFieldValueList)
        else value.enum
        if isinstance(value, DescFieldValueEnum)
        else None
    )
    if not isinstance(enum, DescEnum):
        raise TypeError("Expected an enum field")
    return _enum_mapping(enum)


def _enum_mapping(enum: DescEnum) -> dict[int, str]:

    # remove the enum type prefix from the enum values
    # e.g. FLIGHT_DIRECTION_ASCENDING of the FlightDirection enum will result in a value of ASCENDING
    enum_type_prefix = _camel_to_uppercase(enum.name) + "_"
    return {
        v.number: str(v.name).removeprefix(enum_type_prefix)
        for v in enum.values  # noqa: PD011
    }


def _camel_to_uppercase(name: str) -> str:
    """Convert a camelCase name to an UPPER_CASE name.

    Args:
        name: The name to convert.

    Returns:
        The converted name.

    Examples:
        >>> _camel_to_uppercase("ProcessingLevel")
        'PROCESSING_LEVEL'
        >>> _camel_to_uppercase("SARPolarization")
        'SAR_POLARIZATION'
    """
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).upper()


def is_missing(value: Any) -> bool:
    """Check if a value represents a missing/null value.

    Handles None, np.nan, pd.NA, NaT, and other pandas missing value sentinels.
    This is needed for pandas 3.0+ compatibility where object-dtype columns use
    np.nan instead of None for missing values.
    """
    try:
        return bool(pd.isna(value))
    except ValueError:
        # pd.isna returns either a bool, or an array of bools. In case of an array, converting the result to bool()
        # will raise a ValueError. For an array, we know it's not a missing value, even an array of all NaNs is not
        # a missing value.
        return False
