"""
Functionality for converting protobuf messages to xarray datasets.
"""

import contextlib
from collections.abc import Callable, Sized
from typing import Any, TypeVar

import numpy as np
import xarray as xr
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from numpy.typing import NDArray

from tilebox.datasets.data.datapoint import Datapoint, DatapointPage
from tilebox.datasets.message_pool import get_message_type
from tilebox.datasets.protobuf_conversion.field_types import (
    EnumField,
    ProtobufFieldType,
    ProtoFieldValue,
    enum_mapping_from_field_descriptor,
    infer_field_type,
)

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

    def finalize(
        self, dim_name: str, dataset: xr.Dataset | None = None, ensure_coords: list[str] | None = None
    ) -> xr.Dataset:
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
            f"n_{converter._field_name}": converter._array_dim or 0  # noqa: SLF001
            for converter in self._converters.values()
            if isinstance(converter, _ArrayFieldConverter)
        }
        array_dim_mapping = _combine_dimension_names(array_dims)

        for converter in self._converters.values():
            if isinstance(converter, _ArrayFieldConverter):
                array_dim_name = array_dim_mapping[f"n_{converter._field_name}"][0]  # noqa: SLF001
                converter.finalize(dataset, self.count, (dim_name, array_dim_name))
            else:
                converter.finalize(dataset, self.count, (dim_name,))

        if ensure_coords is not None:
            for coord in ensure_coords:  # promote all variables with the given coord names to coordinates
                if coord in dataset.variables:
                    data = dataset[coord]
                    dataset = dataset.drop_vars(coord)
                    dataset.coords[coord] = data
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
            message_type = get_message_type(datapoint.data.type_url)
            data = message_type.FromString(datapoint.data.value)
            self._data_converter.convert(data)

    def convert_all(self, datapoints: DatapointPage) -> None:
        self._meta_converter.convert_all(datapoints.meta)
        if datapoints.data is not None and datapoints.data.value:
            message_type = get_message_type(datapoints.data.type_url)
            self._data_converter.convert_all([message_type.FromString(val) for val in datapoints.data.value])

    def finalize(self) -> xr.Dataset:
        meta_dataset = self._meta_converter.finalize("time")
        for var in meta_dataset.variables:  # promote all of the fields of the meta message to coordinates
            if var in _TIMESERIES_VAR_REMAPPING:
                data = meta_dataset[var]
                meta_dataset = meta_dataset.drop_vars(str(var))
                meta_dataset.coords[_TIMESERIES_VAR_REMAPPING[str(var)]] = data
            else:
                data = meta_dataset[var]
                if var == "id":
                    data = data.astype(str)
                meta_dataset.coords[var] = data

        dataset = None
        if self._data_converter.count > 0:
            if self._data_converter.count != self._meta_converter.count:
                raise ValueError(
                    "Failed to convert to xarray Dataset: Length mismatch between received data and meta messages"
                )
            dataset = self._data_converter.finalize("time")

        if dataset is not None:
            for meta_coord in meta_dataset.coords:
                if str(meta_coord) in dataset.variables:
                    dataset = dataset.drop_vars(str(meta_coord))
            dataset = xr.merge([meta_dataset, dataset])
        else:
            dataset = meta_dataset

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


class _SimpleFieldConverter(_FieldConverter):
    def __init__(
        self,
        field_name: str,
        field_type: ProtobufFieldType,
        skip_if_empty: bool = False,
    ) -> None:
        """
        A basic field converter for simple fields (i.e. not nested messages) for simple data types
        such as int, float, str or bool

        Args:
            field_name: The name of the field in the protobuf message
            dtype: The numpy data type of the field
        """
        self._field_name = field_name
        self._type = field_type

        self._data: NDArray[Any] = np.zeros((), dtype=self._type.dtype)
        self._empty = skip_if_empty

    def __call__(self, index: int, value: ProtoFieldValue) -> None:
        self._empty = False
        value = self._type.from_proto(value)
        self._data[index, :] = value

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        if self._empty:
            return None
        data = self._data[:count, :]
        if self._type.value_dim == 1:
            data = data.T[0].T  # data[:, :, ..., :, 0]

        if self._type.value_dim_meta is not None:
            dim_name, coords = self._type.value_dim_meta
            if self._type.value_dim != 1:
                dimension_names = (*dimension_names, dim_name)
            if dim_name not in dataset.coords:
                dataset.coords[dim_name] = dim_name, coords

        dataset[self._field_name] = dimension_names, data
        return self._field_name

    def resize(self, buffer_size: int) -> None:
        if self._data.shape == ():  # the first time we actually allocate a buffer
            self._data = np.full((buffer_size, self._type.value_dim), self._type.fill_value, dtype=self._type.dtype)
        else:  # resize the data buffer to the new capacity, by just padding it with zeros at the end
            missing = buffer_size - len(self._data)
            self._data = np.pad(
                self._data,
                ((0, missing), (0, 0)),
                constant_values=self._type.fill_value,  # type: ignore[arg-type]
            )


class _ArrayFieldConverter(_FieldConverter):
    def __init__(
        self,
        field_name: str,
        field_type: ProtobufFieldType,
    ) -> None:
        """
        A field converter for repeated fields that are converted to arrays by adding an extra dimension to the xarray.

        Args:
            field_name: The name of the repeated field in the protobuf message
            field_type: The field type of the repeated field
        """
        self._field_name = field_name
        self._type = field_type
        self._data: NDArray[Any] = np.zeros(())
        self._capacity: int | None = None
        self._array_dim: int | None = None

    def __call__(self, index: int, value: ProtoFieldValue) -> None:
        if not isinstance(value, Sized):
            raise TypeError(f"Expected array field but got {type(value)}")

        if self._array_dim is None or len(value) > self._array_dim:
            self._resize_array_dim(len(value))

        for i, v in enumerate(value):  # type: ignore[arg-type]  # somehow the isinstance(value, Sized) isn't used here
            self._data[index, i, :] = self._type.from_proto(v)

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        if self._data.shape == ():  # Empty
            return None

        data = self._data[:count, :, :]
        if self._type.value_dim == 1:
            data = data.T[0].T  # data[:, :, ..., :, 0]

        if self._type.value_dim_meta is not None:
            extra_dim, coords = self._type.value_dim_meta
            if self._type.value_dim != 1:
                dimension_names = (*dimension_names, extra_dim)
            if extra_dim not in dataset.coords:
                dataset.coords[extra_dim] = extra_dim, coords

        dataset[self._field_name] = dimension_names, data
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
                (self._capacity, self._array_dim, self._type.value_dim), self._type.fill_value, dtype=self._type.dtype
            )
        else:  # resize the data buffer to the new capacity, by just padding it with zeros at the end
            missing_capacity = self._capacity - self._data.shape[0]
            missing_array_dim = self._array_dim - self._data.shape[1]
            self._data = np.pad(
                self._data,
                ((0, missing_capacity), (0, missing_array_dim), (0, 0)),
                constant_values=self._type.fill_value,  # type: ignore[arg-type]
            )


class _EnumFieldConverter(_SimpleFieldConverter):
    def __init__(self, field_name: str, enum_names: dict[int, str]) -> None:
        """
        A field converter for the enum type.

        Args:
            field_name: The name of enum field in the protobuf message
        """
        super().__init__(field_name, EnumField(enum_names))
        self._enum_names = enum_names

    def finalize(self, dataset: xr.Dataset, count: int, dimension_names: tuple[str, ...]) -> str | None:
        field_name = super().finalize(dataset, count, dimension_names)
        if field_name is not None:
            dataset[field_name].attrs["names"] = self._enum_names
        return field_name


def _create_field_converters(message: Message, buffer_size: int) -> dict[str, _FieldConverter]:
    """
    Create a dictionary mapping from field names to field converters for the given protobuf message descriptor.

    Args:
        descriptor: The protobuf message descriptor
        buffer_size: The size of the data arrays to create by the field converters

    Returns:
        A dictionary mapping from field names to field converters
    """
    converters = {}

    for field in message.DESCRIPTOR.fields:
        # if we have an unsupported field type we will get a ValueError, so we just skip those fields
        with contextlib.suppress(ValueError):
            converter = _create_field_converter(field)
            converters[field.name] = converter

    if buffer_size > 0:
        for converter in converters.values():
            converter.resize(buffer_size)
    return converters


def _create_field_converter(field: FieldDescriptor) -> _FieldConverter:
    """
    Create a field converter for the given protobuf field descriptor.

    Args:
        field: The protobuf field descriptor
        buffer_size: The size the data array to create

    Returns:
        A field converter for the given protobuf field descriptor
    """
    # special handling for enums:
    if field.type == FieldDescriptor.TYPE_ENUM:
        if field.label == FieldDescriptor.LABEL_REPEATED:
            raise NotImplementedError("Repeated enum fields are not supported")

        return _EnumFieldConverter(field.name, enum_mapping_from_field_descriptor(field))

    field_type = infer_field_type(field)
    if field.label == FieldDescriptor.LABEL_OPTIONAL:  # simple fields (in proto3 every simple field is optional)
        return _SimpleFieldConverter(field.name, field_type)

    if field.label == FieldDescriptor.LABEL_REPEATED:
        return _ArrayFieldConverter(field.name, field_type)

    raise ValueError(f"Unsupported field type with label {field.label} and type {field.type}")


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
