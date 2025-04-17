import pandas as pd
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
