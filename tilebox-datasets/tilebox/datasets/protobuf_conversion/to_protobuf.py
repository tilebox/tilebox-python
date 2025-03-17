from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
import xarray as xr
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.timestamp_pb2 import Timestamp

from tilebox.datasets.data.datapoint import IngestDatapoints
from tilebox.datasets.datasetsv1 import core_pb2
from tilebox.datasets.protobuf_conversion.field_types import (
    GeobufField,
    ProtobufFieldType,
    ProtoFieldValue,
    TimestampField,
    infer_field_type,
)

IngestionData = Mapping[str, Collection[Any]] | Iterable[tuple[str, Collection[Any]]] | pd.DataFrame | xr.Dataset
DatapointIDs = pd.DataFrame | pd.Series | xr.Dataset | xr.DataArray | np.ndarray | Collection[UUID] | Collection[str]


def to_timeseries_datapoints(data: IngestionData, message_type: type) -> IngestDatapoints:  # noqa: C901, PLR0912
    if not isinstance(data, xr.Dataset) and not isinstance(data, pd.DataFrame):
        try:
            data = pd.DataFrame(data)
        except (TypeError, ValueError):
            raise ValueError("Invalid ingestion data. Failed to convert data to a pandas.DataFrame()") from None

    if "time" not in data:
        raise ValueError("missing time field")

    field_descriptors = message_type.DESCRIPTOR.fields_by_name
    accepted_field_names = set(field_descriptors) | {"time"}

    # let's validate our fields, to make sure that they are all known fields for the given protobuf message
    # and that they are all lists of the same length
    field_lengths = defaultdict(list)
    fields: dict[str, pd.Series | np.ndarray] = {}

    field_names = list(map(str, data))
    if isinstance(data, xr.Dataset):
        # list(dataset) only returns the variables, not the coords, so for xarray we need to add the coords as well
        # but not all coords, we only care abou time for now
        field_names.extend(list(set(map(str, data.coords)) & {"time"}))

    for field_name in field_names:
        values = data[field_name]  # this works for pandas series and xarray data arrays
        if not isinstance(values, pd.Series | xr.DataArray | np.ndarray):
            raise TypeError(
                f"expected a list, pandas.Series or xarray.DataArray of elements for field {field_name}, got {type(values)} instead"
            )

        if field_name not in accepted_field_names:
            raise ValueError(
                f"{field_name} is not a valid field of dataset type {message_type.__name__}. "
                f"Expected one of {', '.join(field_descriptors.keys())}"
            )

        if isinstance(values, xr.DataArray):
            values = values.to_numpy()

        if len(values) == 0:  # empty list, we treat it as not set
            continue

        field_lengths[len(values)].append(field_name)  # to validate all fields have the same length

        # special handling, it's not part of the message descriptor
        if field_name == "time":
            values = convert_values_to_proto(values, TimestampField(), filter_none=False)
        else:
            descriptor = field_descriptors[field_name]
            if descriptor.type == FieldDescriptor.TYPE_ENUM:
                continue  # skip enums, not supported for now in ingestion

            field_type = infer_field_type(descriptor)
            if isinstance(field_type, GeobufField):
                continue  # legacy geometry type, ingestion is only supported for the new geometry type

            if descriptor.label == FieldDescriptor.LABEL_REPEATED:
                values = convert_repeated_values_to_proto(values, field_type)
            else:
                values = convert_values_to_proto(values, field_type, filter_none=False)

        fields[field_name] = values  # type: ignore[assignment]

    # now convert every datapoint to a protobuf message
    metas = []
    values = []

    if len(field_lengths) == 0:  # early return, no actual datapoints to convert
        return IngestDatapoints(meta=metas, data=values)

    if len(field_lengths) > 1:
        msg = [f"- {n}: {', '.join(names)}" for n, names in field_lengths.items()]
        newline = "\n"  # since we can't use it in f-strings due to old python version support
        raise ValueError(f"Inconsistent number of datapoints:{newline}{newline.join(msg)}")

    for datapoint in columnar_to_row_based(fields):
        meta, value = to_ingest_datapoint(message_type, **datapoint)
        metas.append(meta)
        values.append(value)

    return IngestDatapoints(meta=metas, data=values)


def columnar_to_row_based(
    data: dict[str, pd.Series | np.ndarray],
) -> Iterator[dict[str, Any]]:
    if len(data) == 0:
        return

    n_datapoints = len(next(iter(data.values())))
    for i in range(n_datapoints):
        datapoint = {}
        for name, values in data.items():
            datapoint[name] = values[i]
        yield datapoint


def to_ingest_datapoint(
    message_type: type, time: Timestamp, **kwargs: dict[str, Any]
) -> tuple[core_pb2.DatapointMetadata, bytes]:
    meta = core_pb2.DatapointMetadata(event_time=time)
    message = message_type(**kwargs)
    return meta, message.SerializeToString()


def convert_values_to_proto(
    values: np.ndarray | pd.Series, field_type: ProtobufFieldType, filter_none: bool = False
) -> list[ProtoFieldValue]:
    if filter_none:
        return [field_type.to_proto(value) for value in values if value is not None]
    return [field_type.to_proto(value) for value in values]


def convert_repeated_values_to_proto(
    values: np.ndarray | pd.Series | list[np.ndarray], field_type: ProtobufFieldType
) -> Any:
    if isinstance(values, np.ndarray):  # it was an xarray, with potentially padded fill values at the end
        values = trim_trailing_fill_values(values, field_type.fill_value)

    # since repeated fields can have different lengths between datapoints, we can filter out None values here
    return [convert_values_to_proto(repeated_values, field_type, filter_none=True) for repeated_values in values]


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

    assert is_fill_value.ndim == 2, f"Expected a 2D array of fill values, got {is_fill_value.ndim}D"

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
