import string
from datetime import timedelta

import pandas as pd
from hypothesis.strategies import (
    DrawFn,
    binary,
    booleans,
    composite,
    floats,
    integers,
    just,
    lists,
    none,
    one_of,
    text,
    uuids,
)

from tests.data.datasets import example_dataset_type_url
from tests.data.well_known_types import (
    datetime_messages,
    duration_messages,
    geometry_messages,
    processing_levels,
    quaternion_messages,
    shapely_polygons,
    uuid_messages,
    vec3_messages,
)
from tests.example_dataset.example_dataset_pb2 import ExampleDatapoint
from tests.query.pagination import paginations
from tests.query.time_interval import i64_datetimes
from tilebox.datasets.data.datapoint import AnyMessage, IngestResponse, QueryResultPage, RepeatedAny
from tilebox.datasets.datasets.v1 import core_pb2
from tilebox.datasets.query.time_interval import datetime_to_timestamp


@composite
def example_datapoints(draw: DrawFn, generated_fields: bool = False, missing_fields: bool = False) -> ExampleDatapoint:
    """
    A hypothesis strategy for generating random ExampleDatapoint messages

    Args:
        generated_fields: Whether to generate datapoints with all generated fields (id and ingestion_time) set as well.
            If True, datapoints will have all meta fields set. If False, those fields will be set to None, similar
            to how a datapoint for ingestion would look like.
        missing_fields: Whether to generate datapoints with missing custom fields. If True, datapoints
            will randomly have some fields missing. If False, all fields will be set with data.
    """
    # empty one_of() will never generate something, so it means always the other strategy will be used
    maybe_none = none() if missing_fields else one_of()

    return ExampleDatapoint(
        time=draw(datetime_messages()),
        id=(draw(uuid_messages()) if generated_fields else None),
        ingestion_time=(draw(datetime_messages()) if generated_fields else None),
        geometry=draw(geometry_messages()),
        some_string=draw(text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=10) | maybe_none),
        some_int=draw(integers(min_value=1, max_value=100) | maybe_none),
        some_double=draw(floats(min_value=1.0, max_value=100.0) | maybe_none),
        some_time=draw(datetime_messages() | maybe_none),
        some_duration=draw(duration_messages() | maybe_none),
        some_bytes=draw(binary(min_size=1, max_size=10) | maybe_none),
        some_bool=draw(booleans() | maybe_none),
        # well-known types
        some_identifier=draw(uuid_messages() | maybe_none),
        some_vec3=draw(vec3_messages() | maybe_none),
        some_quaternion=draw(quaternion_messages() | maybe_none),
        some_geometry=draw(geometry_messages() | maybe_none),
        # enum
        some_enum=draw(processing_levels() | maybe_none),
        # repeated fields
        some_repeated_string=draw(
            lists(text(alphabet=string.ascii_letters, min_size=1, max_size=10), min_size=1, max_size=5) | maybe_none
        ),
        some_repeated_int=draw(lists(integers(min_value=1, max_value=100), min_size=1, max_size=5) | maybe_none),
        some_repeated_double=draw(lists(floats(min_value=1.0, max_value=100.0), min_size=1, max_size=5) | maybe_none),
        some_repeated_bytes=draw(lists(binary(min_size=1, max_size=10), min_size=1, max_size=5) | maybe_none),
        # only True, to avoid trimming of fill values at the end
        some_repeated_bool=draw(lists(just(True), min_size=1, max_size=5) | maybe_none),
        some_repeated_time=draw(lists(datetime_messages(), min_size=1, max_size=5) | maybe_none),
        some_repeated_duration=draw(lists(duration_messages(), min_size=1, max_size=5) | maybe_none),
        some_repeated_identifier=draw(lists(uuid_messages(), min_size=1, max_size=5) | maybe_none),
        some_repeated_vec3=draw(lists(vec3_messages(), min_size=1, max_size=5) | maybe_none),
        some_repeated_geometry=draw(lists(geometry_messages(), min_size=1, max_size=3) | maybe_none),
    )


@composite
def example_pandas_datapoints(draw: DrawFn) -> pd.DataFrame:
    vec3 = draw(vec3_messages())
    quaternion = draw(quaternion_messages())

    return pd.DataFrame(
        {
            "time": [draw(i64_datetimes)],
            # doesn't include ingestion time and id, because the pandas datapoint is used for testing ingestion
            "some_string": [draw(text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=10))],
            "some_int": [draw(integers(min_value=1, max_value=100))],
            "some_double": [draw(floats(min_value=1.0, max_value=100.0))],
            "some_time": [draw(i64_datetimes)],
            "some_duration": [timedelta(seconds=draw(integers(min_value=0, max_value=1000)))],
            "some_bytes": [draw(binary(min_size=1, max_size=10))],
            "some_bool": [draw(booleans())],
            # well-known types
            "some_identifier": [draw(uuids(version=4))],
            "some_vec3": [(vec3.x, vec3.y, vec3.z)],
            "some_quaternion": [(quaternion.q1, quaternion.q2, quaternion.q3, quaternion.q4)],
            "some_geometry": [draw(shapely_polygons())],
            # enum
            "some_enum": [draw(processing_levels())],
            # repeated fields
            "some_repeated_string": [
                draw(lists(text(alphabet=string.ascii_letters, min_size=1, max_size=10), min_size=1, max_size=5))
            ],
            "some_repeated_int": [draw(lists(integers(min_value=1, max_value=100), min_size=1, max_size=5))],
            "some_repeated_double": [draw(lists(floats(min_value=1.0, max_value=100.0), min_size=1, max_size=5))],
            "some_repeated_bytes": [draw(lists(binary(min_size=1, max_size=10), min_size=1, max_size=5))],
            # here we can use booleans, not only True, since no fill value trimming is done from pandas
            "some_repeated_bool": [draw(lists(booleans(), min_size=1, max_size=5))],
            "some_repeated_time": [draw(lists(i64_datetimes, min_size=1, max_size=5))],
            "some_repeated_duration": [
                [
                    timedelta(seconds=s)
                    for s in draw(lists(integers(min_value=0, max_value=1000), min_size=1, max_size=5))
                ]
            ],
            "some_repeated_identifier": [draw(lists(uuids(version=4), min_size=1, max_size=5))],
            "some_repeated_vec3": [
                [(vec3.x, vec3.y, vec3.z) for vec3 in draw(lists(vec3_messages(), min_size=1, max_size=5))]
            ],
            "some_repeated_geometry": [draw(lists(shapely_polygons(), min_size=1, max_size=3))],
        }
    )


@composite
def anys(draw: DrawFn, generated_fields: bool = False, missing_fields: bool = False) -> AnyMessage:
    """A hypothesis strategy for generating random Any messages"""
    # we need a random byte string here, but let's actually use a valid protobuf message, in this
    # case because its easy to generate let's use a DatapointMetadata message
    datapoint = draw(example_datapoints(generated_fields, missing_fields))
    return AnyMessage(example_dataset_type_url(), datapoint.SerializeToString())


@composite
def repeated_anys(
    draw: DrawFn, generated_fields: bool = False, missing_fields: bool = False, fixed_length: int | None = None
) -> RepeatedAny:
    """A hypothesis strategy for generating random RepeatedAny messages"""
    if fixed_length is not None:
        datapoints = draw(
            lists(example_datapoints(generated_fields, missing_fields), min_size=fixed_length, max_size=fixed_length)
        )
    else:
        datapoints = draw(lists(example_datapoints(generated_fields, missing_fields), min_size=1, max_size=5))
    return RepeatedAny(example_dataset_type_url(), [dp.SerializeToString() for dp in datapoints])


@composite
def datapoint_metadata_messages(draw: DrawFn) -> core_pb2.DatapointMetadata:
    event_time = datetime_to_timestamp(draw(i64_datetimes))
    ingestion_time = datetime_to_timestamp(draw(i64_datetimes))
    data_point_id = str(draw(uuids(version=4)))
    return core_pb2.DatapointMetadata(event_time=event_time, ingestion_time=ingestion_time, id=data_point_id)


@composite
def query_result_pages(
    draw: DrawFn, empty_next_page: bool | None = None, generated_fields: bool = True, missing_fields: bool = False
) -> QueryResultPage:
    """
    A hypothesis strategy for generating random query result pages

    Args:
        empty_next_page: Whether the next page should be empty or not. If None, it will randomly be either an
            empty or non-empty next page.
        generated_fields: Whether to generate datapoints with all generated fields (id and ingestion_time) set as well.
            If True, datapoints will have all meta fields set. If False, those fields will be set to None, similar
            to how a datapoint for ingestion would look like.
        missing_fields: Whether to generate datapoints with missing custom fields. If True, datapoints
            will randomly have some fields missing. If False, all fields will be set with data.
    """
    data = draw(repeated_anys(generated_fields, missing_fields))
    next_page = draw(paginations(empty_next_page))
    byte_size = sum(len(m) for m in data.value)
    return QueryResultPage(data, next_page, byte_size)


@composite
def paginated_query_results(draw: DrawFn) -> list[QueryResultPage]:
    """A hypothesis strategy for generating random datapoint pages for a time interval"""
    # let's generate a couple of pages, that each have a next page set, indicating that there are more pages
    first_pages = draw(lists(query_result_pages(empty_next_page=False), min_size=0, max_size=5))
    last_page = draw(query_result_pages(empty_next_page=True))
    return [*first_pages, last_page]


@composite
def ingest_datapoints_responses(draw: DrawFn) -> IngestResponse:
    """A hypothesis strategy for generating random ingest datapoints responses"""
    num_created = draw(integers(min_value=0, max_value=50))
    num_existing = draw(integers(min_value=0, max_value=50))
    datapoint_ids = draw(
        lists(uuids(), min_size=num_created + num_existing, max_size=num_created + num_existing, unique=True)
    )
    return IngestResponse(num_created, num_existing, datapoint_ids)
