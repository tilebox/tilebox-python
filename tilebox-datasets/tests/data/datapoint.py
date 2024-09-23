import string

from hypothesis.strategies import (
    DrawFn,
    binary,
    booleans,
    composite,
    integers,
    lists,
    none,
    one_of,
    text,
    uuids,
)

from tests.data.datasets import example_dataset_type_url
from tests.data.pagination import paginations
from tests.data.time_interval import i64_datetimes
from tests.data.well_known_types import (
    datetime_messages,
    duration_messages,
    geobuf_messages,
    latlon_messages,
    latlonalt_messages,
    processing_levels,
    quaternion_messages,
    uuid_messages,
    vec3_messages,
)
from tests.example_dataset.example_dataset_pb2 import ExampleDatapoint
from tilebox.datasets.data.datapoint import (
    Any,
    Datapoint,
    DatapointInterval,
    DatapointPage,
    DeleteDatapointsResponse,
    IngestDatapointsResponse,
    RepeatedAny,
)
from tilebox.datasets.data.time_interval import (
    datetime_to_timestamp,
)
from tilebox.datasets.datasetsv1 import core_pb2


@composite
def datapoint_intervals(draw: DrawFn) -> DatapointInterval:
    """A hypothesis strategy for generating random datapoint intervals"""
    start = str(draw(uuids(version=4)))
    end = str(draw(uuids(version=4)))
    start, end = min(start, end), max(start, end)  # make sure start is before end

    start_exclusive = draw(booleans())
    end_inclusive = draw(booleans())

    return DatapointInterval(start, end, start_exclusive, end_inclusive)


@composite
def example_datapoints(draw: DrawFn, missing_fields: bool = False) -> ExampleDatapoint:
    """
    A hypothesis strategy for generating random ExampleDatapoint messages

    Args:
        missing_fields: Whether to generate datapoints with missing fields. If True, datapoints
            will randomly have some fields missing. If False, all fields will be set with data.
    """
    # empty one_of() will never generate something, so it means always the other strategy will be used
    maybe_none = none() if missing_fields else one_of()

    return ExampleDatapoint(
        some_string=draw(text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=10) | maybe_none),
        some_int=draw(integers(min_value=0, max_value=100) | maybe_none),
        some_time=draw(datetime_messages() | maybe_none),
        some_duration=draw(duration_messages() | maybe_none),
        some_repeated_string=draw(
            lists(text(alphabet=string.ascii_letters, min_size=1, max_size=10), min_size=1, max_size=10) | maybe_none
        ),
        some_repeated_int=draw(lists(integers(min_value=-100, max_value=100), min_size=1, max_size=10) | maybe_none),
        some_bytes=draw(binary(min_size=1, max_size=10) | maybe_none),
        some_id=draw(uuid_messages() | maybe_none),
        some_vec3=draw(vec3_messages() | maybe_none),
        some_quaternion=draw(quaternion_messages() | maybe_none),
        some_latlon=draw(latlon_messages() | maybe_none),
        some_latlon_alt=draw(latlonalt_messages() | maybe_none),
        some_geometry=draw(geobuf_messages() | maybe_none),
        some_enum=draw(processing_levels() | maybe_none),
    )


@composite
def anys(draw: DrawFn, missing_fields: bool = False) -> Any:
    """A hypothesis strategy for generating random Any messages"""
    # we need a random byte string here, but let's actually use a valid protobuf message, in this
    # case because its easy to generate let's use a DatapointMetadata message
    datapoint = draw(example_datapoints(missing_fields))
    return Any(example_dataset_type_url(), datapoint.SerializeToString())


@composite
def repeated_anys(draw: DrawFn, missing_fields: bool = False, fixed_length: int | None = None) -> RepeatedAny:
    """A hypothesis strategy for generating random RepeatedAny messages"""
    if fixed_length is not None:
        datapoints = draw(lists(example_datapoints(missing_fields), min_size=fixed_length, max_size=fixed_length))
    else:
        datapoints = draw(lists(example_datapoints(missing_fields), min_size=1, max_size=5))
    return RepeatedAny(example_dataset_type_url(), [dp.SerializeToString() for dp in datapoints])


@composite
def datapoint_metadata_messages(draw: DrawFn) -> core_pb2.DatapointMetadata:
    event_time = datetime_to_timestamp(draw(i64_datetimes))
    ingestion_time = datetime_to_timestamp(draw(i64_datetimes))
    data_point_id = str(draw(uuids(version=4)))
    return core_pb2.DatapointMetadata(event_time=event_time, ingestion_time=ingestion_time, id=data_point_id)


@composite
def datapoints(draw: DrawFn, missing_fields: bool = False) -> Datapoint:
    """A hypothesis strategy for generating random datapoints"""
    meta = draw(datapoint_metadata_messages())
    data = draw(anys(missing_fields))
    return Datapoint(meta, data)


@composite
def datapoint_pages(draw: DrawFn, empty_next_page: bool | None = None, missing_fields: bool = False) -> DatapointPage:
    """
    A hypothesis strategy for generating random datapoints

    Args:
        empty_next_page: Whether the next page should be empty or not. If None, it will randomly be either an
            empty or non-empty next page.
    """
    meta = draw(lists(datapoint_metadata_messages(), min_size=1, max_size=5))
    data = draw(repeated_anys(missing_fields, fixed_length=len(meta)))
    next_page = draw(paginations(empty_next_page))
    byte_size = sum(len(m) for m in data.value)
    return DatapointPage(meta, data, next_page, byte_size)


@composite
def paginated_datapoint_for_interval_responses(draw: DrawFn) -> list[DatapointPage]:
    """A hypothesis strategy for generating random datapoint pages for a time interval"""
    # let's generate a couple of pages, that each have a next page set, indicating that there are more pages
    first_pages = draw(lists(datapoint_pages(empty_next_page=False), min_size=0, max_size=5))
    last_page = draw(datapoint_pages(empty_next_page=True))
    return [*first_pages, last_page]


@composite
def ingest_datapoints_responses(draw: DrawFn) -> IngestDatapointsResponse:
    """A hypothesis strategy for generating random ingest datapoints responses"""
    num_created = draw(integers(min_value=0, max_value=50))
    num_existing = draw(integers(min_value=0, max_value=50))
    datapoint_ids = draw(
        lists(uuids(), min_size=num_created + num_existing, max_size=num_created + num_existing, unique=True)
    )
    return IngestDatapointsResponse(num_created, num_existing, datapoint_ids)


@composite
def delete_datapoints_responses(draw: DrawFn) -> DeleteDatapointsResponse:
    """A hypothesis strategy for generating random delete datapoints responses"""
    num_deleted = draw(integers(min_value=0, max_value=5_000))
    return DeleteDatapointsResponse(num_deleted)
