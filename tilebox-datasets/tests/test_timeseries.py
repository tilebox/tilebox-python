from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import xarray as xr
from hypothesis import assume, given, settings
from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, invariant, rule
from hypothesis.strategies import lists

from _tilebox.errors import ArgumentError, NotFoundError
from tests.data.collection import collection_infos, collection_names
from tests.data.datapoint import example_datapoints, paginated_query_results
from tests.data.datasets import example_dataset_type, example_dataset_type_url
from tests.example_dataset.schema import ExampleDatapoint
from tilebox.datasets import CollectionClient, DatasetClient, field
from tilebox.datasets.data.collection import Collection, CollectionInfo
from tilebox.datasets.data.datapoint import AnyMessage, QueryResultPage
from tilebox.datasets.data.datasets import Dataset
from tilebox.datasets.data.timeseries import TimeseriesDatasetChunk
from tilebox.datasets.query.time_interval import (
    _EMPTY_TIME_INTERVAL,
    TimeInterval,
    _convert_to_datetime,
    timestamp_to_datetime,
)
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.datasets.v1.collections_pb import (
    CreateCollectionRequest,
    DeleteCollectionRequest,
    GetCollectionByNameRequest,
    ListCollectionsRequest,
    ListCollectionsResponse,
)
from tilebox.datasets.v1.core_pb import Collection as CollectionMessage
from tilebox.datasets.v1.core_pb import CollectionInfo as CollectionInfoMessage
from tilebox.datasets.v1.timeseries_pb import TimeseriesDatasetChunk as TimeseriesDatasetChunkMessage


@pytest.mark.parametrize(("start", "end"), [(0, 86400), (-86400, 0), (0.5, 1)])
def test_chunk_preserves_zero_second_timestamps(start: float, end: float) -> None:
    interval = TimeInterval(datetime.fromtimestamp(start, UTC), datetime.fromtimestamp(end, UTC))
    message = TimeseriesDatasetChunkMessage(
        dataset_id=uuid_to_uuid_message(uuid4()),
        collection_id=uuid_to_uuid_message(uuid4()),
        time_interval=interval.to_message(),
    )

    chunk = TimeseriesDatasetChunk.from_message(message)
    assert chunk.time_interval == interval
    assert TimeseriesDatasetChunk.from_binary(chunk.to_binary()) == chunk


@pytest.mark.parametrize("missing_field", ["time_interval", "start_time", "end_time"])
def test_chunk_missing_time_interval_fields(missing_field: str) -> None:
    interval = TimeInterval(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
    message = TimeseriesDatasetChunkMessage(
        dataset_id=uuid_to_uuid_message(uuid4()),
        collection_id=uuid_to_uuid_message(uuid4()),
        time_interval=interval.to_message(),
    )
    if missing_field == "time_interval":
        setattr(message, missing_field, None)
    else:
        setattr(message.time_interval, missing_field, None)

    assert TimeseriesDatasetChunk.from_message(message).time_interval is None


def _mocked_dataset() -> tuple[DatasetClient, MagicMock]:
    service = MagicMock()
    connection = MagicMock()
    connection.client.return_value = service

    # we do not sample/draw from datasets() here, because the values themselves are irrelevant for the tests
    # (we are not testing properties, but rather writing conventional unit tests here, so it doesn't make sense to
    # run them multiple times)
    dataset = DatasetClient(
        connection,
        Dataset(
            id=uuid4(),
            group_id=uuid4(),
            type=example_dataset_type(),
            code_name="example_dataset",
            name="Example Dataset",
            summary="",
            icon="satellite",
            description="",
        ),
    )
    return dataset, service


@settings(max_examples=1)
@given(infos=lists(collection_infos(), min_size=3, max_size=10))
def test_timeseries_dataset_list_collections(infos: list[CollectionInfo]) -> None:
    """Test that the .collections() methods returns a dict of RemoteTimeseriesDatasetCollection objects."""
    # since the output of collections() is a dict we need distinct collection names:
    assume(len({info.collection.name for info in infos}) == len(infos))

    infos = [
        CollectionInfo(
            info.collection,
            info.availability or _EMPTY_TIME_INTERVAL,
            info.count or 0,
        )
        for info in infos
    ]
    dataset, service = _mocked_dataset()
    service.list_collections.return_value = ListCollectionsResponse(data=[info.to_message() for info in infos])

    collections = dataset.collections()

    service.list_collections.assert_called_once_with(
        ListCollectionsRequest(
            dataset_id=uuid_to_uuid_message(dataset._dataset.id), with_availability=True, with_count=True
        )
    )
    assert len(collections) == len(infos)

    for info in infos:
        collection = collections[info.collection.name]
        assert isinstance(collection, CollectionClient), "Expected a RemoteTimeseriesDatasetCollection"
        assert collection.name == info.collection.name, "Name mismatch in collection"
        assert repr(info) in repr(collection), "Expected info to be in collection repr"
        assert collection._info == info, "Expected info to be cached"


@given(collection_names())
@settings(max_examples=1)
def test_timeseries_dataset_get_collection(collection_name: str) -> None:
    dataset, service = _mocked_dataset()
    mocked = _mocked_collection()
    info = mocked.collection_info
    info.collection.name = collection_name
    service.get_collection_by_name.return_value = info.to_message()

    collection = dataset.collection(collection_name)

    service.get_collection_by_name.assert_called_once_with(
        GetCollectionByNameRequest(
            dataset_id=uuid_to_uuid_message(dataset._dataset.id),
            collection_name=collection_name,
            with_availability=True,
            with_count=True,
        )
    )
    assert collection_name in repr(collection), "Expected collection name to be in repr"


@dataclass
class MockedCollection:
    dataset: DatasetClient
    dataset_info: Dataset
    collection: CollectionClient
    collection_info: CollectionInfo
    service: MagicMock


def _mocked_collection() -> MockedCollection:
    dataset, service = _mocked_dataset()

    # we do not sample/draw from collection_infos() here, because the values themselves are irrelevant for the tests
    # (we are not testing properties, but rather writing conventional unit tests here, so it doesn't make sense to
    # run them multiple times)
    collection_info = CollectionInfo(
        collection=Collection(
            id=uuid4(),
            name="some-collection",
        ),
        availability=None,
        count=None,
    )

    service.get_collection_by_name.return_value = collection_info.to_message()
    collection = dataset.collection(collection_info.collection.name)
    collection._info = collection_info
    return MockedCollection(dataset, dataset._dataset, collection, collection_info, service)


def test_timeseries_dataset_collection_info() -> None:
    """Test that .info() of a collection returns the correct CollectionInfo."""
    mocked = _mocked_collection()
    collection = mocked.collection
    info = mocked.collection_info

    assert collection.info() == info


def test_timeseries_dataset_collection_info_cache() -> None:
    """Test that .info() of a collection is cached."""
    mocked = _mocked_collection()
    info = mocked.collection_info
    collection = mocked.collection

    for _ in range(3):  # call three times to ensure caching works
        mocked.service.get_collection_by_name.return_value = info.to_message()
        assert collection.info() == info

    assert mocked.service.get_collection_by_name.call_count == 1, "Expected the info endpoint responses to be cached"


@settings(max_examples=1)
@given(example_datapoints(generated_fields=True, missing_fields=True))
def test_timeseries_dataset_collection_find(expected_datapoint: ExampleDatapoint) -> None:
    """Test that .find() of a collection returns a datapoint as xarray.Dataset."""
    mocked = _mocked_collection()
    collection = mocked.collection

    message = AnyMessage(example_dataset_type_url(), expected_datapoint.to_binary())

    mocked.service.query_by_id.return_value = message.to_message()
    datapoint = collection.find(uuid_message_to_uuid(expected_datapoint.id))

    assert isinstance(datapoint, xr.Dataset)
    assert timestamp_to_datetime(expected_datapoint.time) == _convert_to_datetime(datapoint.coords["time"].item())
    assert timestamp_to_datetime(expected_datapoint.ingestion_time) == _convert_to_datetime(
        datapoint["ingestion_time"].item()
    )
    assert str(uuid_message_to_uuid(expected_datapoint.id)) == datapoint["id"]


def test_timeseries_dataset_collection_find_invalid_id() -> None:
    """Test that .find() of a collection raises a ValueError if the datapoint id is invalid."""
    mocked = _mocked_collection()
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        mocked.collection.find("invalid")

    mocked.service.query_by_id.side_effect = ArgumentError
    with pytest.raises(ValueError, match=r"Invalid datapoint id.*"):
        mocked.collection.find(uuid4())


def test_timeseries_dataset_collection_find_not_found() -> None:
    """Test that .find() of a collection raises a NotFoundError if the datapoint is not found."""
    mocked = _mocked_collection()
    mocked.service.query_by_id.side_effect = NotFoundError
    with pytest.raises(NotFoundError, match=r"No such datapoint.*"):
        mocked.collection.find("14eb91a2-a42f-421f-9397-1dab577f05a9")


@settings(max_examples=1)
@given(example_datapoints(generated_fields=True, missing_fields=True))
def test_timeseries_dataset_find_multiple_collections(expected_datapoint: ExampleDatapoint) -> None:
    """Test that DatasetClient.find() supports querying by mixed collection reference types."""
    dataset, service = _mocked_dataset()

    named_collection = CollectionInfo(Collection(uuid4(), "named-collection"), None, None)
    other_collection = CollectionInfo(Collection(uuid4(), "other-collection"), None, None)

    service.list_collections.return_value = ListCollectionsResponse(
        data=[named_collection.to_message(), other_collection.to_message()]
    )
    message = AnyMessage(example_dataset_type_url(), expected_datapoint.to_binary())
    service.query_by_id.return_value = message.to_message()

    datapoint_id = uuid_message_to_uuid(expected_datapoint.id)
    datapoint = dataset.find(
        datapoint_id,
        [
            named_collection.collection.name,
        ],
    )

    assert isinstance(datapoint, xr.Dataset)
    service.list_collections.assert_called_once_with(
        ListCollectionsRequest(
            dataset_id=uuid_to_uuid_message(dataset._dataset.id), with_availability=True, with_count=True
        )
    )
    request = service.query_by_id.call_args.args[0]
    assert request.dataset_id == uuid_to_uuid_message(dataset._dataset.id)
    assert request.collection_ids == [uuid_to_uuid_message(named_collection.collection.id)]
    assert request.id == uuid_to_uuid_message(datapoint_id)
    assert not request.skip_data


@settings(max_examples=1)
@given(pages=paginated_query_results())
def test_timeseries_dataset_query_multiple_collections(pages: list[QueryResultPage]) -> None:
    """Test that DatasetClient.query() forwards all selected collection ids to the backend query endpoint."""
    dataset, service = _mocked_dataset()

    named_collection = CollectionInfo(Collection(uuid4(), "named-collection"), None, None)
    other_collection = CollectionInfo(Collection(uuid4(), "other-collection"), None, None)

    service.list_collections.return_value = ListCollectionsResponse(
        data=[named_collection.to_message(), other_collection.to_message()]
    )
    service.query.side_effect = [page.to_message() for page in pages]

    interval = TimeInterval(datetime.now(), datetime.now() + timedelta(days=1))
    queried = dataset.query(
        collections=[
            named_collection.collection.name,
        ],
        temporal_extent=interval,
    )

    _assert_datapoints_match(queried, pages)
    service.list_collections.assert_called_once_with(
        ListCollectionsRequest(
            dataset_id=uuid_to_uuid_message(dataset._dataset.id), with_availability=True, with_count=True
        )
    )
    request = service.query.call_args_list[0].args[0]
    assert request.dataset_id == uuid_to_uuid_message(dataset._dataset.id)
    assert request.collection_ids == [uuid_to_uuid_message(named_collection.collection.id)]


@settings(max_examples=1)
@given(pages=paginated_query_results())
def test_timeseries_dataset_query_filter(pages: list[QueryResultPage]) -> None:
    dataset, service = _mocked_dataset()
    service.list_collections.return_value = ListCollectionsResponse()
    service.query.side_effect = [page.to_message() for page in pages]
    interval = TimeInterval(datetime.now(), datetime.now() + timedelta(days=1))

    dataset.query(
        temporal_extent=interval,
        filter=(field("quality") >= 80) | field("quality").is_null(),
    )

    filters = service.query.call_args_list[0].args[0].filters
    assert len(filters.expressions) == 1
    assert filters.expressions[0].logical.operands[0].comparison.field_name == "quality"


def test_timeseries_dataset_query_rejects_invalid_filter_before_request() -> None:
    dataset, service = _mocked_dataset()
    interval = TimeInterval(datetime.now(), datetime.now() + timedelta(days=1))

    with pytest.raises(TypeError, match="Expected a query expression"):
        dataset.query(
            collections=["collection"],
            temporal_extent=interval,
            filter="quality > 80",  # ty: ignore[invalid-argument-type]
        )

    service.list_collections.assert_not_called()
    service.query.assert_not_called()


@patch("tilebox.datasets.sync.pagination.tqdm")
@patch("tilebox.datasets.progress.tqdm")
@settings(deadline=1000, max_examples=3)  # increase deadline to 1s to not timeout because of the progress bar
@given(pages=paginated_query_results())
@pytest.mark.parametrize("show_progress", [True, False])
def test_timeseries_dataset_collection_query(
    tqdm1: MagicMock, tqdm2: MagicMock, pages: list[QueryResultPage], show_progress: bool
) -> None:
    """Test that .load() of a collection returns a dataset as xarray.Dataset."""
    # a mocked tqdm function that can count how many times update() was called
    progress_bar = MagicMock()
    progress_bar.total = 100
    tqdm1.return_value = progress_bar  # support "progress_bar = tqdm()" usage
    tqdm2.return_value = progress_bar
    progress_bar.__enter__.return_value = progress_bar  # support "with tqdm() as progress_bar:" usage

    mocked = _mocked_collection()
    # each call will return the next page in the list
    # the last page will have an empty next_page set, indicating that there are no more pages
    mocked.service.query.side_effect = [page.to_message() for page in pages]
    # the interval doesn't actually matter here, since we mock the response
    interval = TimeInterval(datetime.now(), datetime.now() + timedelta(days=1))
    dataset = mocked.collection.query(temporal_extent=interval, show_progress=show_progress)
    _assert_datapoints_match(dataset, pages)

    if show_progress:
        expected_updates = len(pages) if len(pages) > 1 else 0
        assert progress_bar.update.call_count == expected_updates


@patch("tilebox.datasets.sync.pagination.tqdm")
@settings(deadline=1000, max_examples=3)  # increase deadline to 1s to not timeout because of the progress bar
@given(pages=paginated_query_results())
@pytest.mark.parametrize("show_progress", [True, False])
def test_timeseries_dataset_collection_find_interval(
    tqdm: MagicMock, pages: list[QueryResultPage], show_progress: bool
) -> None:
    """Test that .load() of a collection returns a dataset as xarray.Dataset."""
    # a mocked tqdm function that can count how many times update() was called
    progress_bar = MagicMock()
    progress_bar.total = 100
    tqdm.return_value = progress_bar  # support "progress_bar = tqdm()" usage
    progress_bar.__enter__.return_value = progress_bar  # support "with tqdm() as progress_bar:" usage

    mocked = _mocked_collection()
    # each call will return the next page in the list
    # the last page will have an empty next_page set, indicating that there are no more pages
    mocked.service.query.side_effect = [page.to_message() for page in pages]
    # the interval doesn't actually matter here, since we mock the response
    dataset = mocked.collection._find_interval((uuid4(), uuid4()), show_progress=show_progress)
    _assert_datapoints_match(dataset, pages)

    if show_progress:
        expected_updates = len(pages) if len(pages) > 1 else 0
        assert progress_bar.update.call_count == expected_updates


def _assert_datapoints_match(dataset: xr.Dataset, pages: list[QueryResultPage]) -> None:
    """Assert that the datapoints in the dataset match the given list of protobuf datapoints."""
    assert isinstance(dataset, xr.Dataset)

    datapoints = []
    for page in pages:
        datapoints.extend([page._parse_message(i) for i in range(page.n_datapoints)])

    if len(datapoints) > 0:
        assert dataset.sizes["time"] == len(datapoints)
    for i, datapoint_message in enumerate(datapoints):
        datapoint = dataset.isel(time=i)
        assert timestamp_to_datetime(datapoint_message.time) == _convert_to_datetime(datapoint.coords["time"].item())
        assert timestamp_to_datetime(datapoint_message.ingestion_time) == _convert_to_datetime(
            datapoint["ingestion_time"].item()
        )
        assert str(uuid_message_to_uuid(datapoint_message.id)) == datapoint["id"]


class MockCollectionService:
    """A native collection service double that stores collections in memory."""

    def __init__(self) -> None:
        self.collections: dict[str, CollectionInfoMessage] = {}

    def create_collection(self, req: CreateCollectionRequest) -> CollectionInfoMessage:
        collection = CollectionInfoMessage(
            collection=CollectionMessage(id=uuid_to_uuid_message(uuid4()), name=req.name), availability=None, count=None
        )
        self.collections[req.name] = collection
        return collection

    def get_collection_by_name(self, req: GetCollectionByNameRequest) -> CollectionInfoMessage:
        if req.collection_name in self.collections:
            return self.collections[req.collection_name]
        raise NotFoundError(f"Collection {req.collection_name} not found")

    def delete_collection(self, req: DeleteCollectionRequest) -> None:
        for collection in self.collections.values():
            assert collection.collection is not None
            if collection.collection.id == req.collection_id:
                del self.collections[collection.collection.name]
                return

    def list_collections(self, req: ListCollectionsRequest) -> ListCollectionsResponse:
        _ = req
        return ListCollectionsResponse(data=list(self.collections.values()), owned_collections=len(self.collections))


class CollectionCRUDOperations(RuleBasedStateMachine):
    """
    A state machine that tests the CRUD operations of the Clusters client.

    The rules defined here will be executed in random order by Hypothesis, and each rule can be called any number of
    times. The state of the state machine is defined by the bundles, which are collections of objects that can be
    inserted into the state machine by the rules. Rules can also consume objects from the bundles, which will remove
    them from the state machine state.

    For more information see:
    https://hypothesis.readthedocs.io/en/latest/stateful.html
    """

    def __init__(self) -> None:
        super().__init__()
        dataset_client, service = _mocked_dataset()
        collections = MockCollectionService()
        service.create_collection.side_effect = collections.create_collection
        service.get_collection_by_name.side_effect = collections.get_collection_by_name
        service.delete_collection.side_effect = collections.delete_collection
        service.list_collections.side_effect = collections.list_collections
        self.dataset_client = dataset_client
        self.count_collections = 0

    inserted_collections: Bundle[CollectionClient] = Bundle("collections")

    @rule(target=inserted_collections, collection=collection_infos())
    def get_or_create_collection_enfore_create(self, collection: CollectionInfo) -> CollectionClient:
        collections = self.dataset_client.collections()
        assume(collection.collection.name not in collections)

        self.count_collections += 1
        return self.dataset_client.get_or_create_collection(collection.collection.name)

    @rule(collection=inserted_collections)
    def get_or_create_collection_enfore_get(self, collection: CollectionClient) -> None:
        got = self.dataset_client.get_or_create_collection(collection.name)
        assert got.info() == collection.info()

    @rule(target=inserted_collections, collection=collection_infos())
    def create_collection(self, collection: CollectionInfo) -> CollectionClient:
        collections = self.dataset_client.collections()
        assume(collection.collection.name not in collections)

        self.count_collections += 1
        return self.dataset_client.create_collection(collection.collection.name)

    @rule(collection=inserted_collections)
    def get_collection(self, collection: CollectionClient) -> None:
        got = self.dataset_client.collection(collection.name)
        assert got.info() == collection.info()

    @rule(collection=consumes(inserted_collections))  # consumes -> remove from bundle afterwards
    def delete_collection(self, collection: CollectionClient) -> None:
        self.count_collections -= 1
        assert self.count_collections >= 0
        self.dataset_client.delete_collection(collection)

    @invariant()
    def list_collections(self) -> None:
        collections = self.dataset_client.collections()
        assert len(collections) == self.count_collections


# make pytest pick up the test cases from the state machine
TestCollectionCRUDOperations = CollectionCRUDOperations.TestCase
