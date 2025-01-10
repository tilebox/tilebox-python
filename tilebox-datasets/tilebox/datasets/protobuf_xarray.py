"""
Functionality for converting protobuf messages to xarray datasets.
"""

from collections.abc import Callable, Sized
from typing import Any, TypeVar
from uuid import UUID

import numpy as np
import xarray as xr
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.duration_pb2 import Duration
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp
from numpy.dtypes import ObjectDType, StrDType
from numpy.typing import NDArray
from shapely import MultiPolygon, Polygon

from tilebox.datasets.data.datapoint import Datapoint, DatapointPage
from tilebox.datasets.datasetsv1.well_known_types_pb2 import UUID as UUIDMessage  # noqa: N811
from tilebox.datasets.datasetsv1.well_known_types_pb2 import GeobufData, LatLon, LatLonAlt, Quaternion, Vec3
from tilebox.datasets.message_pool import get_message_type

AnyMessage = TypeVar("AnyMessage", bound=Message)


class MessageToXarrayConverter:
    def __init__(self, initial_capacity: int = 0) -> None:
        """
        A converter for converting arbitrary protobuf messages to a xarray dataset

        Args:
            initial_capacity: The initial capacity (in number of messages) to reserve for the data arrays of each field.
                If the total number of messages is already known in advance, set it to this number
        """
        self._capacity = initial_capacity
        self.count = 0  # number of messages already converted
        self._converters: dict[str, _FieldConverter] | None = None

    def convert(self, message: Message) -> None:
        """
        Convert a single protobuf message and add it to the internal buffer of converted messages

        Args:
            message: The message to convert
        """
        self._ensure_capacity(self.count + 1)
        if self._converters is None:
            self._converters = _create_field_converters(message, buffer_size=self._capacity)
        self._convert(message)

    def convert_all(self, messages: list[AnyMessage]) -> None:
        """
        Convert multiple protobuf messages and add them to the internal buffer of converted messages

        Args:
            messages: The messages to convert
        """
        if len(messages) == 0:
            return

        self._ensure_capacity(self.count + len(messages))
        if self._converters is None:
            self._converters = _create_field_converters(messages[0], buffer_size=self._capacity)
        for message in messages:
            self._convert(message)

    def finalize(self, dim_name: str, dataset: xr.Dataset | None = None) -> xr.Dataset:
        """
        Assemble all converted messages into a final xarray Dataset and return it

        Args:
            dim_name: The name for the dimension of all the messages
            dataset: Optional output dataset to write the data arrays in to

        Returns:
            xr.Dataset: The assembled dataset
        """
        if dataset is None:
            dataset = xr.Dataset()
        if self._converters is None:
            return dataset

        array_dims = {
            converter._array_dim_name: converter._array_dim or 0  # noqa: SLF001
            for converter in self._converters.values()
            if isinstance(converter, _ArrayFieldConverter)
        }
        array_dim_mapping = _combine_dimension_names(array_dims)

        for converter in self._converters.values():
            if isinstance(converter, _ArrayFieldConverter):
                array_dim_name = array_dim_mapping[converter._array_dim_name][0]  # noqa: SLF001
                converter.finalize(dataset, self.count, (dim_name, array_dim_name))
            else:
                converter.finalize(dataset, self.count, (dim_name,))
        return dataset

    def _convert(self, message: Message) -> None:
        """
        Actual internal conversion function for processing a single message. Do not call directly without ensuring
        the converters have been initialized and the buffer resized for the new capacity
        """
        assert self._converters is not None
        assert self.count < self._capacity

        for field, value in message.ListFields():
            self._converters[field.name](self.count, value)
        self.count += 1

    def _ensure_capacity(self, min_capacity: int) -> None:
        if min_capacity <= 0:
            return
        if self._capacity == 0:  # the first time we request a specific capacity
            self._capacity = min_capacity

        new_capacity = self._capacity
        while new_capacity < min_capacity:
            new_capacity *= 2  # double the buffer size until we are large enough

        if new_capacity > self._capacity and self._converters is not None:
            for converter in self._converters.values():
                converter.resize(new_capacity)

        self._capacity = new_capacity


_TIMESERIES_VAR_REMAPPING = {
    "event_time": "time",
}


class TimeseriesToXarrayConverter:
    def __init__(
        self, initial_capacity: int = 0, finalizers: list[Callable[[xr.Dataset], xr.Dataset]] | None = None
    ) -> None:
        """
        A converter for converting timeseries datapoint protobuf messages to a xarray dataset

        Args:
            initial_capacity: The initial capacity (in number of messages) to reserve for the data arrays of each field.
                If the total number of messages is already known in advance, set it to this number
            finalizers: A list of functions to apply to the final xarray dataset after converting all messages
                before returning it in finalize
        """
        self._meta_converter = MessageToXarrayConverter(initial_capacity)
        self._data_converter = MessageToXarrayConverter(initial_capacity)
        self._finalizers = finalizers or []

    def convert(self, datapoint: Datapoint) -> None:
        self._meta_converter.convert(datapoint.meta)
        if datapoint.data is not None and datapoint.data.value:
            # this is here for backwards compatibility:
            if (
                datapoint.data.type_url == "datasets.v1.IseeRadargram"
                and _radargram_as_complex_array not in self._finalizers
            ):
                self._finalizers.append(_radargram_as_complex_array)

            message_type = get_message_type(datapoint.data.type_url)
            data = message_type.FromString(datapoint.data.value)
            self._data_converter.convert(data)

    def convert_all(self, datapoints: DatapointPage) -> None:
        self._meta_converter.convert_all(datapoints.meta)
        if datapoints.data is not None and datapoints.data.value:
            # this is here for backwards compatibility:
            if (
                datapoints.data.type_url == "datasets.v1.IseeRadargram"
                and _radargram_as_complex_array not in self._finalizers
            ):
                self._finalizers.append(_radargram_as_complex_array)

            message_type = get_message_type(datapoints.data.type_url)
            self._data_converter.convert_all([message_type.FromString(val) for val in datapoints.data.value])

    def finalize(self) -> xr.Dataset:
        dataset = self._meta_converter.finalize("time")
        for var in dataset.variables:  # promote all of the fields of the meta message to coordinates
            if var in _TIMESERIES_VAR_REMAPPING:
                data = dataset[var]
                dataset = dataset.drop_vars(str(var))
                dataset.coords[_TIMESERIES_VAR_REMAPPING[str(var)]] = data
            else:
                data = dataset[var]
                if var == "id":
                    data = data.astype(str)
                dataset.coords[var] = data

        if self._data_converter.count > 0:
            if self._data_converter.count != self._meta_converter.count:
                raise ValueError(
                    "Failed to convert to xarray Dataset: Length mismatch between received data and meta messages"
                )
            self._data_converter.finalize("time", dataset)

        for finalizer in self._finalizers:
            dataset = finalizer(dataset)
        return dataset


class _FieldConverter:
    """
    Base class for all field converters.

    A field converter is responsible for converting a single field of a protobuf message
    to a variable in a xarray dataset.
    """

    def __call__(self, index: int, value: float | str | bool | Message) -> None:
        """
        Assign the given value coming from a protobuf message to the data array constructed by this field converter.

        Args:
            index: index of the datapoint in the timeseries
            value: value of the field in the protobuf message
        """

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        """
        Finalize the field conversion and assign the data array to the given xarray dataset.

        Args:
            dataset: The dataset to which the data array should be assigned
            count: Number of messages that have been converted in total
            dimension_names: The names of the dimensions of the data array

        Returns:
            The name of the variable in the dataset to which the data array was assigned or None if the field was empty
        """

    def resize(self, buffer_size: int) -> None:
        """
        Resize the internal buffer to make space for at least buffer_size messages

        Args:
            buffer_size: Minimum number of messages the internal field converter data buffer should hold
        """


FieldType = Message | float | str | bool | bytes | Sized  # Sized -> repeated fields that are converted to arrays


class _SimpleFieldConverter(_FieldConverter):
    def __init__(self, field_name: str, dtype: type | str, skip_if_empty: bool = True) -> None:
        """
        A basic field converter for simple fields (i.e. not nested messages) for simple data types
        such as int, float, str or bool

        Args:
            field_name: The name of the field in the protobuf message
            dtype: The numpy data type of the field
        """
        self._field_name = field_name
        self._dtype, self._fill_value = _to_dtype_and_fill_value(dtype)
        self._data: NDArray[Any] = np.zeros((), dtype=dtype)
        self._empty = skip_if_empty

    def __call__(self, index: int, value: FieldType) -> None:
        self._empty = False
        self._data[index] = value

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        if self._empty:
            return None
        dataset[self._field_name] = dimension_names, self._data[:count]
        return self._field_name

    def resize(self, buffer_size: int) -> None:
        if self._data.shape == ():  # the first time we actually allocate a buffer
            self._data = np.full(buffer_size, self._fill_value, dtype=self._dtype)
        else:  # resize the data buffer to the new capacity, by just padding it with zeros at the end
            missing = buffer_size - len(self._data)
            self._data = np.pad(self._data, (0, missing), constant_values=self._fill_value)


class _TimeFieldConverter(_SimpleFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for time fields.

        Args:
            field_name: The name of the time field.
        """
        super().__init__(field_name, np.int64)

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, Timestamp):
            raise TypeError(f"Expected Timestamp message but got {type(value)}")

        self._empty = False
        self._data[index] = value.seconds * 10**9 + value.nanos

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        if self._empty:
            return None
        datetimes = self._data[:count].astype("datetime64[ns]")
        dataset[self._field_name] = dimension_names, datetimes
        return self._field_name


class _TimeDeltaFieldConverter(_SimpleFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for time delta fields (durations).

        Args:
            field_name: The name of the time field.
        """
        super().__init__(field_name, np.int64)

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, Duration):
            raise TypeError(f"Expected Duration message but got {type(value)}")

        self._empty = False
        self._data[index] = value.seconds * 10**9 + value.nanos

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        if self._empty:
            return None
        timedeltas = self._data[:count].astype("timedelta64[ns]")
        dataset[self._field_name] = dimension_names, timedeltas
        return self._field_name


class _UUIDFieldConverter(_SimpleFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for UUID fields. Converting a UUID sent as 16 bytes to a string.

        Args:
            field_name: The name of the uuid field.
        """
        super().__init__(field_name, "<U36")

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, UUIDMessage):
            raise TypeError(f"Expected UUID message but got {type(value)}")

        self._empty = False
        if len(value.uuid) > 0:
            self._data[index] = str(UUID(bytes=value.uuid))


def _to_dtype_and_fill_value(dtype: type | str) -> tuple[np.dtype, str | int]:
    npdtype = np.dtype(dtype)
    if type(npdtype) is StrDType:
        return npdtype, ""
    if type(npdtype) is ObjectDType:
        return npdtype, None  # type: ignore[return-value]
    return npdtype, 0


class _ArrayFieldConverter(_FieldConverter):
    def __init__(
        self,
        field_name: str,
        dtype: type | str,
        array_dim_name: str | None = None,
        fixed_dims: dict[str, int] | None = None,
    ) -> None:
        """
        A field converter for fields that are converted to arrays.

        This is the case for repeated fields (e.g. repeated int32), for bytes fields, or for sub messages like Vec3
        and Quaternions.

        Args:
            field_name: The name of the repeated field in the protobuf message
            dtype: The numpy data type of the field
        """
        self._field_name = field_name
        self._dtype, self._fill_value = _to_dtype_and_fill_value(dtype)
        self._data: NDArray[Any] = np.zeros(())
        self._capacity: int | None = None
        self._array_dim: int | None = None
        self._array_dim_name = f"n_{field_name}" if array_dim_name is None else array_dim_name
        self._fixed_dims = fixed_dims or {}

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, Sized):
            raise TypeError(f"Expected array field but got {type(value)}")
        if self._array_dim is None or len(value) > self._array_dim:
            self._resize_array_dim(len(value))
        self._data[index, : len(value)] = value

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        if self._data.shape == ():  # Empty
            return None
        dimension_names = dimension_names + tuple(self._fixed_dims.keys())
        if len(dimension_names) < 2 + len(self._fixed_dims):
            raise ValueError("missing dimension name for array field")
        dataset[self._field_name] = dimension_names, self._data[:count, :]
        return self._field_name

    def resize(self, buffer_size: int) -> None:
        self._capacity = buffer_size
        # we don't know the actual size of the array dimension yet, need to wait for the first message
        if self._array_dim is not None:
            self._resize()

    def _resize_array_dim(self, array_dim: int) -> None:
        self._array_dim = array_dim
        if self._capacity is not None:
            self._resize()

    def _resize(self) -> None:
        assert self._capacity is not None
        assert self._array_dim is not None
        if self._data.shape == ():  # the first time we actually allocate a buffer
            self._data = np.full(
                (self._capacity, self._array_dim, *self._fixed_dims.values()), self._fill_value, dtype=self._dtype
            )
        else:  # resize the data buffer to the new capacity, by just padding it with zeros at the end
            missing_capacity = self._capacity - self._data.shape[0]
            missing_array_dim = self._array_dim - self._data.shape[1]
            no_pad = [(0, 0) for _ in self._fixed_dims]
            self._data = np.pad(
                self._data, ((0, missing_capacity), (0, missing_array_dim), *no_pad), constant_values=self._fill_value
            )


class _Vec3FieldConverter(_ArrayFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for the Vec3 message type.

        Args:
            field_name: The name of the Vec3 field in the protobuf message
        """
        super().__init__(field_name, float, "vec3")

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, Vec3):
            raise TypeError(f"Expected Vec3 message but got {type(value)}")

        super().__call__(index, (value.x, value.y, value.z))

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        field_name = super().finalize(dataset, count, dimension_names)
        # if we have a Vec3 field in a dataset we also want to label the vec3 dimension appropriately
        if field_name is not None and "vec3" not in dataset.coords:
            dataset.coords["vec3"] = "vec3", ["x", "y", "z"]
        return field_name


class _QuaternionFieldConverter(_ArrayFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for the Quaternion message type.

        Args:
            field_name: The name of the Quaternion field in the protobuf message
        """
        super().__init__(field_name, float, "quaternion")

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, Quaternion):
            raise TypeError(f"Expected Quaternion message but got {type(value)}")

        super().__call__(index, (value.q1, value.q2, value.q3, value.q4))

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        field_name = super().finalize(dataset, count, dimension_names)
        # if we have a Quaternion field in a dataset we also want to label the quaternion dimension appropriately
        if field_name is not None and "quaternion" not in dataset.coords:
            dataset.coords["quaternion"] = "quaternion", ["q1", "q2", "q3", "q4"]
        return field_name


class _LatLonFieldConverter(_ArrayFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for the LatLon message type.

        Args:
            field_name: The name of the Vec3 field in the protobuf message
        """
        super().__init__(field_name, float, "latlon")

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, LatLon):
            raise TypeError(f"Expected LatLon message but got {type(value)}")

        super().__call__(index, (value.latitude, value.longitude))

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        field_name = super().finalize(dataset, count, dimension_names)
        # if we have a LatLon field in a dataset we also want to label the latlon dimension appropriately
        if field_name is not None and "latlon" not in dataset.coords:
            dataset.coords["latlon"] = "latlon", ["latitude", "longitude"]
        return field_name


class _LatLonAltFieldConverter(_ArrayFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for the LatLonAlt message type.

        Args:
            field_name: The name of the LatLonAlt field in the protobuf message
        """
        super().__init__(field_name, float, "lat_lon_alt")

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, LatLonAlt):
            raise TypeError(f"Expected LatLonAlt message but got {type(value)}")

        super().__call__(index, (value.latitude, value.longitude, value.altitude))

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        field_name = super().finalize(dataset, count, dimension_names)
        # if we have a LatLonAlt field in a dataset we also want to label the lat_lon_alt dimension appropriately
        if field_name is not None and "lat_lon_alt" not in dataset.coords:
            dataset.coords["lat_lon_alt"] = "lat_lon_alt", ["latitude", "longitude", "altitude"]
        return field_name


class _BytesFieldConverter(_ArrayFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for the protobuf bytes type.

        Args:
            field_name: The name of the bytes field in the protobuf message
        """
        super().__init__(field_name, np.uint8)

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, bytes):
            raise TypeError(f"Expected bytes field but got {type(value)}")

        super().__call__(index, np.frombuffer(value, dtype=np.uint8))


class _EnumFieldConverter(_SimpleFieldConverter):
    def __init__(self, field_name: str, enum_names: dict[int, str]) -> None:
        """
        A field converter for the enum type.

        Args:
            field_name: The name of enum field in the protobuf message
        """
        super().__init__(field_name, np.uint8)  # we support up to 256 different enum values for now
        self._enum_names = enum_names

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        field_name = super().finalize(dataset, count, dimension_names)
        if field_name is not None:
            # convert the numeric enum values to the corresponding string names
            int_values = dataset[field_name]
            dataset[field_name] = (
                int_values.dims,
                np.vectorize(lambda i: self._enum_names.get(i, ""))(int_values.values),
            )
            dataset[field_name].attrs["enum_dict"] = ";".join(
                f"{name}: {value}" for value, name in self._enum_names.items()
            )
        return field_name


class _GeobufFieldConverter(_SimpleFieldConverter):
    def __init__(self, field_name: str) -> None:
        """
        A field converter for Geobuf Protobuf fields. Right now only geometry data is supported.

        Converts the GeobufData message to a shapely polygon.
        """
        super().__init__(field_name, object)

    def __call__(self, index: int, value: FieldType) -> None:
        if not isinstance(value, GeobufData):
            raise TypeError(f"Expected GeobufData message but got {type(value)}")

        self._empty = False
        self._data[index] = _parse_geobuf(value)


def _parse_geobuf(data: GeobufData) -> Polygon | MultiPolygon:
    if data.dimensions != 2:
        raise ValueError(f"Expected GeobufData message with 2 dimensions but got {data.dimensions}")

    coords = np.asarray(data.geometry.coords)
    if data.geometry.type == GeobufData.Geometry.Type.TYPE_POLYGON:
        return _decode_polygon_geobuf(coords, np.asarray(data.geometry.lengths), data.precision)
    if data.geometry.type == GeobufData.Geometry.Type.TYPE_MULTIPOLYGON:
        return _decode_multipolygon_geobuf(coords, np.asarray(data.geometry.lengths), data.precision)

    raise ValueError(f"Unsupported geometry type {data.geometry.type}")


def _decode_multipolygon_geobuf(coords: np.ndarray, lengths: np.ndarray, precision: int) -> MultiPolygon:
    """Convert geobuf encoded coordinates and lengths to a shapely multipolygon.

    A multipolygon is a sequence of polygons. The lengths array tells us how many polygons we
    have, and also how many individual coordiante rings each polygon consists of.

    We can therefore iterate over that and then use _decode_polygon_geobuf to convert
    each polygon individually, and afterwards assemble it back together.
    """
    polygons = []

    # let's now construct our multipolygon as a sequence of polygons
    n_polys = lengths[0]
    curr_len_idx = 1  # first value is the number of polygons
    curr_coord_idx = 0
    while curr_len_idx < len(lengths):
        n_rings = lengths[curr_len_idx]
        curr_len_idx += 1

        poly_lengths = lengths[curr_len_idx : curr_len_idx + n_rings]
        n_poly_coords = np.sum(poly_lengths) * 2  # * 2 for lat/lon
        poly_coords = coords[curr_coord_idx : curr_coord_idx + n_poly_coords]
        polygons.append(_decode_polygon_geobuf(poly_coords, poly_lengths, precision))

        curr_len_idx += n_rings
        curr_coord_idx += n_poly_coords

    if len(polygons) != n_polys:
        raise ValueError("Number of polygons does not match the number of polygons in the lengths array")

    return MultiPolygon(polygons)


def _decode_polygon_geobuf(coords: np.ndarray, lengths: np.ndarray, precision: int) -> Polygon:
    """Convert geobuf encoded coordinates and lengths to a shapely polygon.

    A polygon is a sequence of rings (list of points). The simplest case is just one ring,
    which is the outer shell of the polygon. All subsequent rings are holes in the interior
    of the polygon.

    Args:
        coords: Flat list of coordinates in geobuf encoding
        lengths: Lengths of the individual rings that make up this polygon. Correspond to
            the coords.
        precision: Precision multiplier for the coordinates

    Returns:
        A shapely polygon
    """
    rings = []
    curr_idx = 0

    for ring_length in lengths:
        rings.append(_decode_coords_ring(coords[curr_idx : curr_idx + ring_length * 2], precision))  # * 2 for lon/lat
        curr_idx += ring_length * 2

    if len(rings) < 1:
        raise ValueError("Polygon needs to consist of at least one ring")

    return Polygon(shell=rings[0], holes=rings[1:])


def _decode_coords_ring(coords: np.ndarray, precision: int) -> list[tuple[float, float]]:
    """Convert a geobuf encoded coord ring to a list of points

    Geobuf encoding is as follows:
    All values are stored as integers, by multiplying them with the precision (e.g. 10^7 for precision 7)
    Then all values are delta encoded, i.e. the first value is stored as is, and all following values are
    stored as the difference to the previous value.
    The values are then zigzag encoded, e.g. first an x value, then a y value, then the next x value, etc.
    All polygons need to be closed, i.e. the first and last point need to be the same. However, geobuf skips
    that last (duplicated) value, so we need to add it back in.

    Returns:
        A list of points
    """
    precision = 10**precision
    lons = np.cumsum(coords[::2]) / precision
    lats = np.cumsum(coords[1::2]) / precision
    points = list(zip(lons, lats, strict=True))
    points.append(points[0])  # close the ring
    return points


def _create_field_converters(message: Message, buffer_size: int) -> dict[str, _FieldConverter]:
    """
    Create a dictionary mapping from field names to field converters for the given protobuf message descriptor.

    Args:
        descriptor: The protobuf message descriptor
        buffer_size: The size of the data arrays to create by the field converters

    Returns:
        A dictionary mapping from field names to field converters
    """
    converters = {field.name: _create_field_converter(field) for field in message.DESCRIPTOR.fields}
    if buffer_size > 0:
        for converter in converters.values():
            converter.resize(buffer_size)
    return converters


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


def _create_field_converter(field: FieldDescriptor) -> _FieldConverter:  # noqa: PLR0911, C901, PLR0912
    """
    Create a field converter for the given protobuf field descriptor.

    Args:
        field: The protobuf field descriptor
        buffer_size: The size the data array to create

    Returns:
        A field converter for the given protobuf field descriptor
    """
    if field.label == FieldDescriptor.LABEL_OPTIONAL:  # simple fields (in proto3 every simple field is optional)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "Vec3":
            return _Vec3FieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "Quaternion":
            return _QuaternionFieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "Timestamp":
            return _TimeFieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "Duration":
            return _TimeDeltaFieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "LatLon":
            return _LatLonFieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "LatLonAlt":
            return _LatLonAltFieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "GeobufData":
            return _GeobufFieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_MESSAGE and field.message_type.name == "UUID":
            return _UUIDFieldConverter(field.name)
        if field.type in _PROTOBUF_TYPE_TO_NUMPY_TYPE:
            skip_if_empty = field.type == FieldDescriptor.TYPE_STRING
            return _SimpleFieldConverter(field.name, _PROTOBUF_TYPE_TO_NUMPY_TYPE[field.type], skip_if_empty)
        if field.type == FieldDescriptor.TYPE_BYTES:
            return _BytesFieldConverter(field.name)
        if field.type == FieldDescriptor.TYPE_ENUM:
            # remove the enum type prefix from the enum values
            enum_type_prefix = _camel_to_uppercase(field.enum_type.name) + "_"
            return _EnumFieldConverter(
                field.name,
                {v.number: str(v.name).removeprefix(enum_type_prefix) for v in field.enum_type.values},
            )
    elif field.label == FieldDescriptor.LABEL_REPEATED and field.type in _PROTOBUF_TYPE_TO_NUMPY_TYPE:  # array fields
        return _ArrayFieldConverter(field.name, _PROTOBUF_TYPE_TO_NUMPY_TYPE[field.type])

    # if we reach this point we have an unsupported field type, in that case we just skip that field by
    # returning a dummy field converter that doesn't do anything
    return _FieldConverter()


# A mapping from protobuf field types to the corresponding numpy data types
_PROTOBUF_TYPE_TO_NUMPY_TYPE = {
    FieldDescriptor.TYPE_DOUBLE: float,
    FieldDescriptor.TYPE_FLOAT: np.float32,
    FieldDescriptor.TYPE_INT64: int,
    FieldDescriptor.TYPE_UINT64: np.uint64,
    FieldDescriptor.TYPE_INT32: np.int32,
    FieldDescriptor.TYPE_BOOL: bool,
    FieldDescriptor.TYPE_STRING: object,  # use object to allow for variable length strings
}


def _lookup_array_dimensions(messages: list[Message]) -> dict[str, int]:
    """Return the maximum length as well as a dimension name of each array field in the given list of protobuf messages.

    The maximum length is determined by looking at all messages in the list and finding the maximum length for each
    field.

    Args:
        messages: The protobuf messages for which to lookup the maximum occurring array lengths

    Raises:
        ValueError: If given an empty list of messages

    Returns:
        Maximum length of each array field by its field name, or an empty dict if no array fields were found
    """
    if len(messages) == 0:
        raise ValueError("Cannot create field converters for empty list of messages")
    descriptor = messages[0].DESCRIPTOR
    names = [  # get the names of all array fields
        field.name
        for field in descriptor.fields
        if (field.label == FieldDescriptor.LABEL_REPEATED and field.type in _PROTOBUF_TYPE_TO_NUMPY_TYPE)
        or field.type == FieldDescriptor.TYPE_BYTES
    ]
    if len(names) == 0:  # don't iterate over all messages if there are no array fields
        return {}

    # and then find the maximum length of each array field
    # important: we want to loop over all messages only once, thats why we do it for all names at once
    sizes = tuple({0} for _ in range(len(names)))
    for message in messages:
        for i, name in enumerate(names):
            sizes[i].add(len(getattr(message, name, ())))  # if a message doesn't have a field it is an empty array

    return {name: max(sizes[i]) for i, name in enumerate(names)}


def _combine_dimension_names(array_dimensions: dict[str, int]) -> dict[str, tuple[str, int]]:
    """Assign dimension names to the given array dimensions by their field_names.

    The dimension names default to n_<field_name>. However there is a special case for arrays with the same dimensions:
    If one field is called <field_name> and another <field_name>_<some_suffix>, then the dimension name will be
    n_<field_name>. E.g. the array fields int_metrics and int_metrics_count would share the dimension name
    n_int_metrics if they have the same size.

    Args:
        array_dimensions: The array dimension mapping (field_name: dimension size) to assign dimension names to

    Returns:
        Dict mapping from field names to dimension names and sizes
    """
    dimension_names = {}
    for dim_name, size in array_dimensions.items():
        dimension_names[dim_name] = (dim_name, size)
        for other_dim_name, other_size in array_dimensions.items():
            # strip the last character from the field name because to account for plural forms, e.g. metric and metrics
            if other_dim_name != dim_name and size == other_size and dim_name.startswith(other_dim_name[:-1]):
                dimension_names[dim_name] = (other_dim_name, size)  # overwrite the default entry

    return dimension_names


# this is here for backwards compatibility, since we used to perform specific conversions for certain datasets
# and are now stuck with this. We should remove this eventually by refactoring IseeRadargrams to use a new
# WellKnownType message instead
def _radargram_as_complex_array(ds: xr.Dataset) -> xr.Dataset:
    """Convert (and interpret) the radargram field in a Dataset from a byte array to a complex array

    Assumes that the byte array is a series of consecutive 16-bit integers, representing the imaginary and real parts
    in that order.
    This means we have 4 bytes per complex number:
    byte0 byte1 byte2 byte3
    ---imag---- ---real----

    Args:
        ds: The dataset to apply the radargram conversion to

    Returns:
        xr.Dataset: The same dataset, but with the radargram field converted to a complex array
    """
    if "radargram" not in ds:
        return ds

    as_ints = np.frombuffer(ds.radargram.values, np.int16).reshape(ds.radargram.shape[0], -1)
    as_complex = as_ints[:, ::2] * np.complex64(1j) + as_ints[:, 1::2]
    ds["radargram"] = ds.radargram.dims, as_complex
    return ds
