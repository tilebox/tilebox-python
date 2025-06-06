from pathlib import Path
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis.strategies import lists
from numpy.testing import assert_array_equal
from shapely import MultiPolygon, Polygon
from xarray.testing import assert_equal

from tests.data.datapoint import datapoint_pages, datapoints, example_datapoints
from tests.example_dataset.example_dataset_pb2 import ExampleDatapoint
from tilebox.datasets.data.datapoint import Datapoint, DatapointPage
from tilebox.datasets.data.time_interval import timestamp_to_datetime, us_to_datetime
from tilebox.datasets.datasetsv1.well_known_types_pb2 import GeobufData, ProcessingLevel
from tilebox.datasets.protobuf_xarray import MessageToXarrayConverter, TimeseriesToXarrayConverter, _parse_geobuf


@given(example_datapoints(missing_fields=False))
def test_convert_datapoint(datapoint: ExampleDatapoint) -> None:
    converter = MessageToXarrayConverter()
    converter.convert(datapoint)
    dataset = converter.finalize("time")

    assert dataset.sizes["time"] == 1
    assert dataset.sizes["vec3"] == 3
    assert dataset.sizes["quaternion"] == 4
    assert dataset.sizes["latlon"] == 2
    assert dataset.sizes["lat_lon_alt"] == 3
    assert dataset.sizes["n_some_repeated_string"] == len(datapoint.some_repeated_string)
    assert dataset.sizes["n_some_repeated_int"] == len(datapoint.some_repeated_int)
    assert dataset.sizes["n_some_bytes"] == len(datapoint.some_bytes)

    dataset = dataset.isel(time=0)  # select the only datapoint in the dataset
    assert dataset.some_string.item() == datapoint.some_string
    assert dataset.some_int.item() == datapoint.some_int
    time = dataset.some_time.item()  # timestamp in nanoseconds from the numpy/xarray dataset
    assert us_to_datetime(time // 1000) == timestamp_to_datetime(datapoint.some_time)
    assert dataset.some_duration.item() == int(datapoint.some_duration.seconds * 10**9 + datapoint.some_duration.nanos)

    assert_array_equal(dataset.some_repeated_string.to_numpy(), datapoint.some_repeated_string)
    assert_array_equal(dataset.some_repeated_int.to_numpy(), datapoint.some_repeated_int)
    assert dataset.some_bytes.to_numpy().tobytes() == datapoint.some_bytes
    assert dataset.some_id.item() == str(UUID(bytes=datapoint.some_id.uuid))
    assert_array_equal(
        dataset.some_vec3.to_numpy(), [datapoint.some_vec3.x, datapoint.some_vec3.y, datapoint.some_vec3.z]
    )
    assert_array_equal(
        dataset.some_quaternion.to_numpy(),
        [
            datapoint.some_quaternion.q1,
            datapoint.some_quaternion.q2,
            datapoint.some_quaternion.q3,
            datapoint.some_quaternion.q4,
        ],
    )
    assert_array_equal(
        dataset.some_latlon.to_numpy(), [datapoint.some_latlon.latitude, datapoint.some_latlon.longitude]
    )
    assert_array_equal(
        dataset.some_latlon_alt.to_numpy(),
        [datapoint.some_latlon_alt.latitude, datapoint.some_latlon_alt.longitude, datapoint.some_latlon_alt.altitude],
    )
    assert isinstance(dataset.some_geometry.item(), Polygon)
    expected_level = {v: k for k, v in ProcessingLevel.items()}[datapoint.some_enum].removeprefix("PROCESSING_LEVEL_")
    assert dataset.some_enum.item() == expected_level


@given(datapoints(missing_fields=True))
def test_convert_timeseries_datapoint(datapoint: Datapoint) -> None:
    converter = TimeseriesToXarrayConverter()
    converter.convert(datapoint)
    dataset = converter.finalize()

    assert dataset.sizes["time"] == 1
    assert dataset.id.item() == datapoint.meta.id
    event_time = dataset.time.item() // 1000
    assert us_to_datetime(event_time) == timestamp_to_datetime(datapoint.meta.event_time)
    ingestion_time = dataset.ingestion_time.item() // 1000
    assert us_to_datetime(ingestion_time) == timestamp_to_datetime(datapoint.meta.ingestion_time)


@given(lists(example_datapoints(missing_fields=True), min_size=5, max_size=30))
def test_convert_datapoints(
    datapoints: list[ExampleDatapoint],
) -> None:
    converter = MessageToXarrayConverter()
    converter.convert_all(datapoints)
    dataset = converter.finalize("time")

    assert dataset.sizes["time"] == len(datapoints)

    # since fields are randomly missing, it can also be a field is missing for all datapoints
    # in which case it won't show up in the xarray dataset at all, which is why we have to check for this
    if "some_repeated_string" in dataset:
        n_some_repeated_string = max(len(dp.some_repeated_string) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_string"] == n_some_repeated_string

    if "some_repeated_int" in dataset:
        n_some_repeated_int = max(len(dp.some_repeated_int) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_int"] == n_some_repeated_int

    if "some_bytes" in dataset:
        n_some_bytes = max(len(dp.some_bytes) for dp in datapoints)
        assert dataset.sizes["n_some_bytes"] == n_some_bytes

    if "some_id" in dataset:
        for uuid in dataset.some_id.to_numpy():
            assert isinstance(uuid, str)

    # strings should be stored as object arrays, with None as the fill value if missing
    if "some_string" in dataset:
        for string in dataset.some_string.to_numpy():
            assert string is None or isinstance(string, str)
    if "some_repeated_string" in dataset:
        for string in dataset.some_repeated_string.to_numpy().ravel():
            assert string is None or isinstance(string, str)


@given(datapoint_pages(empty_next_page=True, missing_fields=True))
def test_convert_timeseries_datapoints(page: DatapointPage) -> None:
    converter = TimeseriesToXarrayConverter()
    converter.convert_all(page)
    dataset = converter.finalize()

    assert dataset.sizes["time"] == len(page.meta)
    for i in range(len(page.meta)):
        datapoint = dataset.isel(time=i)
        meta = page.meta[i]
        assert datapoint.id.item() == meta.id
        event_time = datapoint.time.item() // 1000
        assert us_to_datetime(event_time) == timestamp_to_datetime(meta.event_time)
        ingestion_time = datapoint.ingestion_time.item() // 1000
        assert us_to_datetime(ingestion_time) == timestamp_to_datetime(meta.ingestion_time)


@given(lists(example_datapoints(missing_fields=True), min_size=1, max_size=10))
@settings(max_examples=10)
def test_convert_datapoints_all_at_once_or_one_by_one_same_result(
    datapoints: list[ExampleDatapoint],
) -> None:
    converter1 = MessageToXarrayConverter()
    converter2 = MessageToXarrayConverter()
    converter1.convert_all(datapoints)
    for dp in datapoints:
        converter2.convert(dp)

    dataset1 = converter1.finalize("time")
    dataset2 = converter2.finalize("time")

    assert_equal(dataset1, dataset2)


def _read_geobuf(name: str) -> GeobufData:
    file = Path(__file__).parent / "testdata" / "geobuf" / name

    with file.open("rb") as f:
        data = f.read()

    obj = GeobufData()
    obj.ParseFromString(data)
    return obj


def test_decode_polygon_geobuf() -> None:
    poly_geobuf = _read_geobuf("polygon.binpb")

    poly = _parse_geobuf(poly_geobuf)
    assert poly.bounds == (pytest.approx(-180.0), pytest.approx(65.808014), pytest.approx(180.0), pytest.approx(90.0))


def test_decode_multipolygon_geobuf() -> None:
    multipoly_geobuf = _read_geobuf("multipolygon.binpb")

    poly = _parse_geobuf(multipoly_geobuf)
    assert isinstance(poly, MultiPolygon)
    sub_polys = list(poly.geoms)
    assert len(sub_polys) == 2, "Expected 2 sub-polygons"
    assert sub_polys[0].bounds == (
        pytest.approx(-180.0),
        pytest.approx(57.88233),
        pytest.approx(-123.409134),
        pytest.approx(83.292342425),
    )
    assert sub_polys[1].bounds == (
        pytest.approx(126.83469),
        pytest.approx(62.794425427),
        pytest.approx(180.0),
        pytest.approx(84.15669),
    )


def test_decode_multipolygon_with_holes_geobuf() -> None:
    multipoly_geobuf = _read_geobuf("multipolygon_with_holes.binpb")

    poly = _parse_geobuf(multipoly_geobuf)
    assert isinstance(poly, MultiPolygon)
    sub_polys = list(poly.geoms)
    assert len(sub_polys) == 2, "Expected 2 sub-polygons"

    assert sub_polys[0].bounds == (
        pytest.approx(-180.0),
        pytest.approx(-89.999987328),
        pytest.approx(180),
        pytest.approx(89.552340092),
    )
    assert len(sub_polys[0].interiors) == 1, "Expected one hole in subpolygon 0"
    assert sub_polys[0].interiors[0].bounds == (
        pytest.approx(0),
        pytest.approx(80.1859136),
        pytest.approx(55.376515584),
        pytest.approx(85.43048645),
    )

    assert sub_polys[1].bounds == (
        pytest.approx(0),
        pytest.approx(-89.690675287),
        pytest.approx(1.547255492),
        pytest.approx(-85.05115885),
    )
