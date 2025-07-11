from collections.abc import Sized
from datetime import timedelta
from typing import Any
from uuid import UUID

import numpy as np
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.duration_pb2 import Duration
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp
from numpy import dtypes as npdtypes
from pandas.core.tools.datetimes import DatetimeScalar, to_datetime
from pandas.core.tools.timedeltas import to_timedelta
from shapely import from_wkb

from tilebox.datasets.datasets.v1.well_known_types_pb2 import UUID as UUIDMessage  # noqa: N811
from tilebox.datasets.datasets.v1.well_known_types_pb2 import Geometry, LatLon, LatLonAlt, Quaternion, Vec3

ProtoFieldValue = Message | float | str | bool | bytes | Sized | None

_FILL_VALUES_BY_DTYPE = {
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
    npdtypes.DateTime64DType: np.datetime64("NaT"),
    npdtypes.TimeDelta64DType: np.timedelta64("NaT"),
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
        super().__init__(np.uint8)  # we support up to 256 different enum values for now
        self._values_to_name = name_lookup
        self._names_to_value = {name: value for value, name in name_lookup.items()}

    def from_proto(self, value: ProtoFieldValue) -> int:
        if not isinstance(value, int):
            raise TypeError(f"Expected int message but got {type(value)}")
        return value  # we don't parse the value when loading, to avoid having huge arrays of strings

    def to_proto(self, value: str | int) -> int:
        if isinstance(value, (str, np.str_)):
            return self._names_to_value[value]
        if int(value) not in self._values_to_name:
            raise ValueError(f"Invalid enum value {value}")  # during ingestion, we can raise an error here
        return value


class TimestampField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__("datetime64[ns]")

    def from_proto(self, value: ProtoFieldValue) -> int:
        if not isinstance(value, Timestamp):
            raise TypeError(f"Expected Timestamp message but got {type(value)}")
        return value.seconds * 10**9 + value.nanos

    def to_proto(self, value: DatetimeScalar) -> Timestamp | None:
        if value is None or (isinstance(value, np.datetime64) and np.isnat(value)):
            return None
        # we use pandas to_datetime function to handle a variety of input types that can be coerced to datetimes
        seconds, nanos = divmod(to_datetime(value, utc=True).value, 10**9)
        return Timestamp(seconds=seconds, nanos=nanos)


class TimeDeltaField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__("timedelta64[ns]")

    def from_proto(self, value: ProtoFieldValue) -> int:
        if not isinstance(value, Duration):
            raise TypeError(f"Expected Duration message but got {type(value)}")
        return value.seconds * 10**9 + value.nanos

    def to_proto(self, value: str | float | timedelta | np.timedelta64) -> Duration | None:
        if value is None or (isinstance(value, np.timedelta64) and np.isnat(value)):
            return None
        # we use pandas to_timedelta function to handle a variety of input types that can be coerced to timedeltas
        seconds, nanos = divmod(to_timedelta(value).value, 10**9)  # type: ignore[arg-type]
        return Duration(seconds=seconds, nanos=nanos)


class UUIDField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__("<U36")

    def from_proto(self, value: ProtoFieldValue) -> str:
        if not isinstance(value, UUIDMessage):
            raise TypeError(f"Expected UUID message but got {type(value)}")
        return str(UUID(bytes=value.uuid))

    def to_proto(self, value: str | UUID) -> UUIDMessage | None:
        if not value:  # None or empty string
            return None

        if isinstance(value, str):
            value = UUID(value)

        return UUIDMessage(uuid=value.bytes)


class GeometryField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(object)

    def from_proto(self, value: ProtoFieldValue) -> Any:
        if not isinstance(value, Geometry):
            raise TypeError(f"Expected Geometry message but got {type(value)}")
        return from_wkb(value.wkb)

    def to_proto(self, value: Any) -> Geometry | None:
        if value is None:
            return None
        return Geometry(wkb=value.wkb)


class Vec3Field(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=3, value_dim_meta=("vec3", ["x", "y", "z"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float, float]:
        if not isinstance(value, Vec3):
            raise TypeError(f"Expected Vec3 message but got {type(value)}")
        return value.x, value.y, value.z

    def to_proto(self, value: tuple[float, float, float]) -> Vec3 | None:
        if value is None or np.all(np.isnan(value)):
            return None
        return Vec3(x=value[0], y=value[1], z=value[2])


class QuaternionField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=4, value_dim_meta=("quaternion", ["q1", "q2", "q3", "q4"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float, float, float]:
        if not isinstance(value, Quaternion):
            raise TypeError(f"Expected Quaternion message but got {type(value)}")
        return value.q1, value.q2, value.q3, value.q4

    def to_proto(self, value: tuple[float, float, float, float]) -> Quaternion | None:
        if value is None or np.all(np.isnan(value)):
            return None
        return Quaternion(q1=value[0], q2=value[1], q3=value[2], q4=value[3])


class LatLonField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=2, value_dim_meta=("latlon", ["latitude", "longitude"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float]:
        if not isinstance(value, LatLon):
            raise TypeError(f"Expected LatLon message but got {type(value)}")
        return value.latitude, value.longitude

    def to_proto(self, value: tuple[float, float]) -> LatLon | None:
        if value is None or np.all(np.isnan(value)):
            return None
        return LatLon(latitude=value[0], longitude=value[1])


class LatLonAltField(ProtobufFieldType):
    def __init__(self) -> None:
        super().__init__(float, value_dim=3, value_dim_meta=("lat_lon_alt", ["latitude", "longitude", "altitude"]))

    def from_proto(self, value: ProtoFieldValue) -> tuple[float, float, float]:
        if not isinstance(value, LatLonAlt):
            raise TypeError(f"Expected LatLonAlt message but got {type(value)}")

        return value.latitude, value.longitude, value.altitude

    def to_proto(self, value: tuple[float, float, float]) -> LatLonAlt | None:
        if value is None or np.all(np.isnan(value)):
            return None
        return LatLonAlt(latitude=value[0], longitude=value[1], altitude=value[2])


# A mapping from protobuf field types to the corresponding numpy data types
_PROTOBUF_TYPE_TO_NUMPY_TYPE = {
    FieldDescriptor.TYPE_DOUBLE: float,
    FieldDescriptor.TYPE_FLOAT: np.float32,
    FieldDescriptor.TYPE_INT64: int,
    FieldDescriptor.TYPE_UINT64: np.uint64,
    FieldDescriptor.TYPE_INT32: np.int32,
    FieldDescriptor.TYPE_STRING: object,  # use object to allow for variable length strings
    FieldDescriptor.TYPE_BYTES: object,  # use object to allow for variable length bytes
}

_MESSAGE_NAMES_TO_FIELDS = {
    "google.protobuf.Timestamp": TimestampField(),
    "google.protobuf.Duration": TimeDeltaField(),
    "datasets.v1.UUID": UUIDField(),
    "datasets.v1.Geometry": GeometryField(),
    "datasets.v1.Vec3": Vec3Field(),
    "datasets.v1.Quaternion": QuaternionField(),
    "datasets.v1.LatLon": LatLonField(),
    "datasets.v1.LatLonAlt": LatLonAltField(),
}


def infer_field_type(field: FieldDescriptor) -> ProtobufFieldType:
    if field.type == FieldDescriptor.TYPE_MESSAGE:
        message_name = field.message_type.full_name
        if message_name not in _MESSAGE_NAMES_TO_FIELDS:
            raise ValueError(f"Unsupported message type {message_name}")

        return _MESSAGE_NAMES_TO_FIELDS[message_name]

    if field.type == FieldDescriptor.TYPE_ENUM:
        return EnumField(enum_mapping_from_field_descriptor(field))

    if field.type == FieldDescriptor.TYPE_BOOL:
        return BoolField()  # special handling, since we need to convert numpy bools to python bools

    if field.type not in _PROTOBUF_TYPE_TO_NUMPY_TYPE:
        raise ValueError(f"Unsupported field type {field.type}")

    return ProtobufFieldType(_PROTOBUF_TYPE_TO_NUMPY_TYPE[field.type])


def enum_mapping_from_field_descriptor(field: FieldDescriptor) -> dict[int, str]:
    """Create a mapping from enum values to their names.

    Args:
        field: The field descriptor to create the mapping for. Must be of type FieldDescriptor.TYPE_ENUM.
    """
    if field.type != FieldDescriptor.TYPE_ENUM:
        raise ValueError("Expected field to be of type FieldDescriptor.TYPE_ENUM")

    # remove the enum type prefix from the enum values
    # e.g. FLIGHT_DIRECTION_ASCENDING of the FlightDirection enum will result in a value of ASCENDING
    enum_type_prefix = _camel_to_uppercase(field.enum_type.name) + "_"
    return {
        v.number: str(v.name).removeprefix(enum_type_prefix)
        for v in field.enum_type.values  # noqa: PD011  # enum_type is not a numpy array, even though ruff thinks it is
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
    """
    return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_").upper()
