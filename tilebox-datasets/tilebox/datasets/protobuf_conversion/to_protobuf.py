from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from typing import Any, TypeVar, cast
from uuid import UUID

import numpy as np
import pandas as pd
import xarray as xr
from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message

from tilebox.datasets.protobuf_conversion.field_types import (
    ProtobufFieldType,
    ProtoFieldValue,
    ScalarProtoFieldValue,
    infer_field_type,
    is_missing,
)

Record = Mapping[str, Any]
Column = Sequence[Any] | np.ndarray | pd.Series
ColumnarData = Mapping[str, Column]
IngestionData = ColumnarData | Iterable[Record] | pd.DataFrame | xr.Dataset
DatapointIDs = pd.DataFrame | pd.Series | xr.Dataset | xr.DataArray | np.ndarray | Collection[UUID] | Collection[str]
_MessageT = TypeVar("_MessageT", bound=Message)


def to_messages(
    data: IngestionData,
    message_type: type[_MessageT],
    required_fields: list[str] | None = None,
    ignore_fields: list[str] | None = None,
) -> list[_MessageT]:
    """Convert supported ingestion inputs into protobuf messages.

    Mappings are interpreted as column-oriented data. Iterable inputs are
    interpreted as records, with one mapping per datapoint. DataFrames and
    xarray Datasets are adapted to records without passing values through a
    second tabular representation.

    Missing optional values and absent record keys leave the protobuf field
    unset. Required fields must be present and non-missing in every record.
    """
    required = set(required_fields or [])
    ignore = set(ignore_fields or [])
    field_descriptors_by_name = cast(Descriptor, message_type.DESCRIPTOR).fields_by_name
    records = _iter_records(data, field_descriptors_by_name, ignore)
    return _records_to_messages(records, message_type, field_descriptors_by_name, required, ignore)


def marshal_messages(messages: list[Message]) -> list[bytes]:
    return [m.SerializeToString(deterministic=True) for m in messages]


def _iter_records(
    data: IngestionData,
    descriptors: Mapping[str, FieldDescriptor],
    ignore: set[str],
) -> Iterator[Record]:
    """Adapt each supported input representation to an iterator of records."""
    if isinstance(data, xr.Dataset):
        yield from _xarray_records(data, descriptors, ignore)
        return
    if isinstance(data, pd.DataFrame):
        yield from _dataframe_records(data, descriptors, ignore)
        return
    if isinstance(data, Mapping):
        yield from _columnar_records(cast(ColumnarData, data), descriptors, ignore)
        return

    for index, record in enumerate(data):
        if not isinstance(record, Mapping):
            raise TypeError(
                f"Record-oriented ingestion data must contain mappings, but record {index} is {type(record).__name__}"
            )
        try:
            _validate_field_names(record, descriptors, ignore)
        except (TypeError, ValueError) as error:
            raise type(error)(f"Record {index}: {error}") from error
        yield record


def _dataframe_records(
    data: pd.DataFrame,
    descriptors: Mapping[str, FieldDescriptor],
    ignore: set[str],
) -> Iterator[Record]:
    """Yield DataFrame rows positionally without coercing object values."""
    all_field_names = list(data.columns)
    field_names = _validate_field_names(data.columns, descriptors, ignore)
    if len(set(field_names)) != len(field_names):
        raise ValueError("Ingestion DataFrame contains duplicate field names")
    positions = [all_field_names.index(field_name) for field_name in field_names]
    for values in data.itertuples(index=False, name=None):
        yield {field_name: values[position] for field_name, position in zip(field_names, positions, strict=True)}


def _xarray_records(
    data: xr.Dataset,
    descriptors: Mapping[str, FieldDescriptor],
    ignore: set[str],
) -> Iterator[Record]:
    """Yield xarray datapoints while removing padding from repeated fields."""
    field_names = [*data.data_vars]
    if "time" in data.coords and "time" not in field_names:
        field_names.append("time")
    validated_names = _validate_field_names(field_names, descriptors, ignore)

    columns: dict[str, Column] = {}
    for field_name in validated_names:
        values = data[field_name].to_numpy()
        descriptor = descriptors.get(field_name)
        if descriptor is not None and descriptor.is_repeated:
            field_type = infer_field_type(descriptor)
            values = trim_trailing_fill_values(values, field_type.fill_value)
        columns[field_name] = values
    yield from _transpose_columns(columns, validated_names)


def _columnar_records(
    data: ColumnarData,
    descriptors: Mapping[str, FieldDescriptor],
    ignore: set[str],
) -> Iterator[Record]:
    """Transpose column-oriented data into records after checking its shape."""
    field_names = _validate_field_names(data, descriptors, ignore)
    yield from _transpose_columns(data, field_names)


def _transpose_columns(data: ColumnarData, field_names: list[str]) -> Iterator[Record]:
    """Validate and positionally transpose selected columns into records."""
    columns: list[Column] = []
    lengths: dict[int, list[str]] = {}
    for field_name in field_names:
        values = data[field_name]
        if isinstance(values, str | bytes | bytearray) or not isinstance(values, Sequence | np.ndarray | pd.Series):
            raise TypeError(f"Column {field_name!r} must be an ordered sequence of values")
        columns.append(values)
        lengths.setdefault(len(values), []).append(field_name)

    if len(lengths) > 1:
        details = "\n".join(f"- {length}: {', '.join(names)}" for length, names in lengths.items())
        raise ValueError(f"Inconsistent number of datapoints:\n{details}")
    for row in zip(*columns, strict=True):
        yield dict(zip(field_names, row, strict=True))


def _validate_field_names(
    field_names: Iterable[object],
    descriptors: Mapping[str, FieldDescriptor],
    ignore: set[str],
) -> list[str]:
    """Validate dataset field names and return the fields to ingest."""
    result: list[str] = []
    for field_name in field_names:
        if not isinstance(field_name, str):
            raise TypeError(f"Dataset field names must be strings, got {type(field_name).__name__}")
        if field_name in ignore:
            continue
        if field_name not in descriptors:
            raise ValueError(f"{field_name} is not a valid dataset field. Expected one of {', '.join(descriptors)}")
        result.append(field_name)
    return result


def _records_to_messages(
    records: Iterable[Record],
    message_type: type[_MessageT],
    descriptors: Mapping[str, FieldDescriptor],
    required: set[str],
    ignore: set[str],
) -> list[_MessageT]:
    """Convert records and add the record index to conversion errors."""
    return [
        _record_to_message_with_context(indexed_record, message_type, descriptors, required, ignore)
        for indexed_record in enumerate(records)
    ]


def _record_to_message_with_context(
    indexed_record: tuple[int, Record],
    message_type: type[_MessageT],
    descriptors: Mapping[str, FieldDescriptor],
    required: set[str],
    ignore: set[str],
) -> _MessageT:
    """Convert one record and add its index to conversion errors."""
    index, record = indexed_record
    try:
        return _record_to_message(record, message_type, descriptors, required, ignore)
    except (TypeError, ValueError) as error:
        raise type(error)(f"Record {index}: {error}") from error


def _record_to_message(
    record: Record,
    message_type: type[_MessageT],
    descriptors: Mapping[str, FieldDescriptor],
    required: set[str],
    ignore: set[str],
) -> _MessageT:
    """Convert one field-name-validated record into a protobuf message."""
    missing_required = [name for name in required if name not in record or is_missing(record[name])]
    if missing_required:
        raise ValueError(f"Missing required field(s): {', '.join(sorted(missing_required))}")

    values: dict[str, ProtoFieldValue] = {}
    for field_name, value in record.items():
        if field_name in ignore or is_missing(value):
            continue
        descriptor = descriptors[field_name]
        field_type = infer_field_type(descriptor)
        try:
            if descriptor.is_repeated:
                converted = _convert_repeated_value(value, field_type)
            else:
                converted = field_type.to_proto(value)
        except (TypeError, ValueError) as error:
            raise type(error)(f"Field {field_name!r}: {error}") from error
        if converted is None:
            if field_name in required:
                raise ValueError(f"Field {field_name!r}: Invalid value for required field")
            continue
        values[field_name] = converted
    return message_type(**values)


def _convert_repeated_value(value: Any, field_type: ProtobufFieldType) -> list[ScalarProtoFieldValue]:
    """Convert one repeated field, dropping missing/unrepresentable elements."""
    if isinstance(value, str | bytes | bytearray | Mapping) or not isinstance(value, Iterable):
        raise TypeError("Expected an iterable of values")
    converted = (field_type.to_proto(element) for element in value if not is_missing(element))
    return [cast(ScalarProtoFieldValue, element) for element in converted if element is not None]


def trim_trailing_fill_values(values: np.ndarray, fill_value: Any) -> list[np.ndarray]:
    """
    Strip trailing fill values from a numpy array of datapoints.

    This is necessary because our xarray conversion pads datapoints with trailing fill values to make sure each
    datapoint has the same length (that of the longest datapoint). However, we don't want to include those trailing
    values when ingesting the data.

    Args:
        values: Numpy array of datapoints.
        fill_value: The fill value for the field (inferred from its type).

    Returns:
        List of datapoints, potentially each with different length.
    """
    is_fill_value = np.equal(values, fill_value)
    # special handling for np.nan since (np.nan == np.nan) is False
    if np.issubdtype(values.dtype, np.floating):
        is_fill_value |= np.isnan(values)
    elif np.issubdtype(values.dtype, np.timedelta64) or np.issubdtype(values.dtype, np.datetime64):
        is_fill_value |= np.isnat(values)

    if is_fill_value.ndim == 3:  # nested messages that have a third dimension
        is_fill_value = is_fill_value.all(-1)

    if is_fill_value.ndim != 2:
        raise ValueError(f"Expected a 2D array of fill values, got {is_fill_value.ndim}D")

    if np.all(is_fill_value):
        # we only got fill values, which only makes sense if they really are encoded in the protobuf
        return list(values)

    rows = []
    for row, row_fill_values in zip(values, is_fill_value, strict=True):
        (fill_value_indices,) = np.where(~row_fill_values)
        if len(fill_value_indices) > 0:
            rows.append(row[: np.max(fill_value_indices) + 1])
        else:
            rows.append(row)
    return rows


def extract_datapoint_ids(datapoints: DatapointIDs) -> list[UUID]:
    if isinstance(datapoints, pd.DataFrame | xr.Dataset):
        datapoints = datapoints["id"]

    if isinstance(datapoints, xr.DataArray):
        datapoints = datapoints.to_numpy()

    return [UUID(datapoint) if isinstance(datapoint, str) else datapoint for datapoint in datapoints]
