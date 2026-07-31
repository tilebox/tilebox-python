from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from hypothesis import given
from hypothesis.strategies import lists

from tests.data.datapoint import example_datapoints, example_pandas_datapoints
from tests.example_dataset.example_dataset_pb2 import ExampleDatapoint
from tilebox.datasets.protobuf_conversion.protobuf_xarray import MessageToXarrayConverter
from tilebox.datasets.protobuf_conversion.to_protobuf import to_messages


@given(lists(example_datapoints(generated_fields=True, missing_fields=False), min_size=1, max_size=5))
def test_xarray_dataset_to_protobuf_messages(messages: list[ExampleDatapoint]) -> None:
    dataset = _to_dataset(messages)

    ignore_fields = ["id", "ingestion_time"]
    converted = to_messages(dataset, ExampleDatapoint, required_fields=["time"], ignore_fields=ignore_fields)

    assert len(converted) == len(messages)
    for converted_message, expected_message in zip(converted, messages, strict=True):
        for field in expected_message.DESCRIPTOR.fields:
            if field.name in ignore_fields:
                assert not converted_message.HasField(field.name)
                continue

            assert getattr(expected_message, field.name) == getattr(converted_message, field.name), (
                f"Field {field.name} mismatch"
            )


def _to_dataset(datapoints: list[ExampleDatapoint]) -> xr.Dataset:
    converter = MessageToXarrayConverter()
    converter.convert_all(datapoints)
    return converter.finalize("time", ensure_coords=["time", "id", "ingestion_time"])


@given(lists(example_pandas_datapoints(), min_size=1, max_size=5))
def test_pandas_to_protobuf_messages(datapoints: list[pd.DataFrame]) -> None:
    dataframe = pd.concat(datapoints)
    converted = to_messages(dataframe, ExampleDatapoint)
    assert len(converted) == len(datapoints)


def test_record_oriented_data_preserves_absent_fields_and_filters_missing_values() -> None:
    time = datetime(2026, 7, 31, tzinfo=timezone.utc)
    converted = to_messages(
        [
            {
                "time": time,
                "some_bool": True,
                "some_int": 4,
                "some_repeated_int": [1, None, np.nan, 2],
            },
            {"time": time, "some_bool": np.nan},
        ],
        ExampleDatapoint,
        required_fields=["time"],
    )

    assert converted[0].some_bool is True
    assert converted[0].some_int == 4
    assert converted[0].some_repeated_int == [1, 2]
    assert converted[1].some_bool is False
    assert converted[1].some_int == 0


def test_record_oriented_data_requires_every_record_to_have_required_fields() -> None:
    with pytest.raises(ValueError, match=r"Record 1: Missing required field.*time"):
        to_messages(
            [{"time": datetime(2026, 7, 31, tzinfo=timezone.utc)}, {"some_int": 1}],
            ExampleDatapoint,
            required_fields=["time"],
        )


def test_record_oriented_data_rejects_required_values_that_convert_to_unset() -> None:
    with pytest.raises(ValueError, match="Record 0: Field 'some_identifier': Invalid value for required field"):
        to_messages(
            [{"some_identifier": ""}],
            ExampleDatapoint,
            required_fields=["some_identifier"],
        )


def test_dataframe_missing_values_leave_optional_fields_unset() -> None:
    time = datetime(2026, 7, 31, tzinfo=timezone.utc)
    dataframe = pd.DataFrame([{"time": time, "some_bool": True}, {"time": time}])

    converted = to_messages(dataframe, ExampleDatapoint, required_fields=["time"])

    assert converted[0].some_bool is True
    assert converted[1].some_bool is False


def test_iterable_of_column_tuples_is_rejected_as_invalid_records() -> None:
    with pytest.raises(TypeError, match="record 0 is tuple"):
        to_messages([("time", [datetime(2026, 7, 31, tzinfo=timezone.utc)])], ExampleDatapoint)  # type: ignore[arg-type]


def test_ignored_columns_do_not_participate_in_shape_validation() -> None:
    converted = to_messages(
        {"time": [datetime(2026, 7, 31, tzinfo=timezone.utc)], "id": []},
        ExampleDatapoint,
        required_fields=["time"],
        ignore_fields=["id"],
    )

    assert len(converted) == 1


def test_conversion_errors_include_record_and_field_context() -> None:
    with pytest.raises(TypeError, match="Record 0: Field 'some_repeated_int': Expected an iterable"):
        to_messages([{"some_repeated_int": 1}], ExampleDatapoint)
