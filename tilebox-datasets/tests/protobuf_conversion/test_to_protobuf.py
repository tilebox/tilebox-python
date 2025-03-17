import pandas as pd
import xarray as xr
from hypothesis import given
from hypothesis.strategies import lists

from tests.data.datapoint import DatapointPage, datapoint_pages, example_pandas_datapoints
from tests.example_dataset.example_dataset_pb2 import ExampleDatapoint
from tilebox.datasets.protobuf_conversion.protobuf_xarray import TimeseriesToXarrayConverter
from tilebox.datasets.protobuf_conversion.to_protobuf import to_timeseries_datapoints


@given(datapoint_pages(missing_fields=False))
def test_xarray_dataset_to_timeseries_datapoints(datapoints: DatapointPage) -> None:
    dataset = _to_dataset(datapoints)

    converted = to_timeseries_datapoints(dataset, ExampleDatapoint)

    assert len(converted.meta) == len(datapoints.meta)
    assert len(converted.data) == len(datapoints.data.value)

    for i in range(len(datapoints.meta)):
        assert datapoints.meta[i].event_time == converted.meta[i].event_time, "Event time mismatch"

        expected_message = ExampleDatapoint()
        expected_message.ParseFromString(datapoints.data.value[i])

        converted_message = ExampleDatapoint()
        converted_message.ParseFromString(converted.data[i])

        for field in expected_message.DESCRIPTOR.fields:
            if field.name == "some_enum":  # enum ingestion not implemented yet
                continue
            assert getattr(expected_message, field.name) == getattr(converted_message, field.name), (
                f"Field {field.name} mismatch"
            )


def _to_dataset(datapoints: DatapointPage) -> xr.Dataset:
    converter = TimeseriesToXarrayConverter()
    converter.convert_all(datapoints)
    return converter.finalize()


@given(lists(example_pandas_datapoints(), min_size=1, max_size=5))
def test_pandas_to_timeseries_datapoints(datapoints: list[pd.DataFrame]) -> None:
    dataframe = pd.concat(datapoints)
    converted = to_timeseries_datapoints(dataframe, ExampleDatapoint)
    assert len(converted.meta) == len(datapoints)
    assert len(converted.data) == len(datapoints)
