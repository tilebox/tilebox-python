from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import xarray as xr
from attr import dataclass
from hypothesis import assume, given, settings
from hypothesis.stateful import Bundle, RuleBasedStateMachine, invariant, rule
from hypothesis.strategies import lists
from promise import Promise

from _tilebox.grpc.error import ArgumentError, NotFoundError
from tests.data.collection import collection_infos, collection_names
from tests.data.datapoint import datapoints, paginated_datapoint_for_interval_responses
from tests.data.datasets import example_dataset_type
from tilebox.datasets import TimeseriesCollection, TimeseriesDataset
from tilebox.datasets.data.collection import Collection, CollectionInfo
from tilebox.datasets.data.datapoint import Datapoint, DatapointPage
from tilebox.datasets.data.datasets import Dataset
from tilebox.datasets.data.time_interval import (
    _EMPTY_TIME_INTERVAL,
    TimeInterval,
    _convert_to_datetime,
    timestamp_to_datetime,
)
from tilebox.datasets.data.uuid import uuid_to_uuid_message
from tilebox.datasets.datasetsv1.collections_pb2 import (
    CreateCollectionRequest,
    GetCollectionByNameRequest,
    ListCollectionsRequest,
)
from tilebox.datasets.datasetsv1.collections_pb2_grpc import CollectionServiceStub
from tilebox.datasets.datasetsv1.core_pb2 import Collection as CollectionMessage
from tilebox.datasets.datasetsv1.core_pb2 import CollectionInfo as CollectionInfoMessage
from tilebox.datasets.datasetsv1.core_pb2 import CollectionInfos as CollectionInfosMessage
from tilebox.datasets.service import TileboxDatasetService


def _mocked_dataset() -> tuple[TimeseriesDataset, MagicMock]:
    service = MagicMock()

    # we do not sample/draw from datasets() here, because the values themselves are irrelevant for the tests
    # (we are not testing properties, but rather writing conventional unit tests here, so it doesn't make sense to
    # run them multiple times)
    dataset = TimeseriesDataset(
        service,
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
    # mock a protobuf message response value for the gRPC endpoint:
    service.get_collections.return_value = Promise.resolve(infos)

    collections = dataset.collections()

    service.get_collections.assert_called_once_with(dataset._dataset.id, True, True)
    assert len(collections) == len(infos)

    for info in infos:
        collection = collections[info.collection.name]
        assert isinstance(collection, TimeseriesCollection), "Expected a RemoteTimeseriesDatasetCollection"
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
    service.get_collection_by_name.return_value = Promise.resolve(info)

    collection = dataset.collection(collection_name)

    service.get_collection_by_name.assert_called_once_with(dataset._dataset.id, collection_name, True, True)
    assert collection_name in repr(collection), "Expected collection name to be in repr"


@dataclass
class MockedCollection:
    dataset: TimeseriesDataset
    dataset_info: Dataset
    collection: TimeseriesCollection
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

    collection = dataset.collection(collection_info.collection.name)
    collection._info = collection_info
    collection._use_legacy_api = True  # tests or for the legacy endpoints still
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
        mocked.service.get_collection_by_name.return_value = Promise.resolve(info)
        assert collection.info() == info

    assert mocked.service.get_collection_by_name.call_count == 1, "Expected the info endpoint responses to be cached"


@settings(max_examples=1)
@given(datapoints())
def test_timeseries_dataset_collection_find(expected_datapoint: Datapoint) -> None:
    """Test that .find() of a collection returns a datapoint as xarray.Dataset."""
    mocked = _mocked_collection()
    collection = mocked.collection
    meta = expected_datapoint.meta

    mocked.service.get_datapoint_by_id.return_value = Promise.resolve(expected_datapoint)
    datapoint = collection.find(meta.id)

    assert isinstance(datapoint, xr.Dataset)
    assert timestamp_to_datetime(meta.event_time) == _convert_to_datetime(datapoint.coords["time"].item())
    assert timestamp_to_datetime(meta.ingestion_time) == _convert_to_datetime(datapoint.coords["ingestion_time"].item())
    assert meta.id == datapoint.coords["id"]


def test_timeseries_dataset_collection_find_invalid_id() -> None:
    """Test that .find() of a collection raises a ValueError if the datapoint id is invalid."""
    mocked = _mocked_collection()
    mocked.service.get_datapoint_by_id.side_effect = ArgumentError
    with pytest.raises(ValueError, match="Invalid datapoint id.*"):
        mocked.collection.find("invalid")


def test_timeseries_dataset_collection_find_not_found() -> None:
    """Test that .find() of a collection raises a NotFoundError if the datapoint is not found."""
    mocked = _mocked_collection()
    mocked.service.get_datapoint_by_id.side_effect = NotFoundError
    with pytest.raises(NotFoundError, match="No such datapoint.*"):
        mocked.collection.find("14eb91a2-a42f-421f-9397-1dab577f05a9")


@patch("tilebox.datasets.sync.pagination.tqdm")
@patch("tilebox.datasets.progress.tqdm")
@settings(deadline=1000, max_examples=3)  # increase deadline to 1s to not timeout because of the progress bar
@given(pages=paginated_datapoint_for_interval_responses())
@pytest.mark.parametrize(("show_progress", "skip_data"), [(True, True), (True, False), (False, True), (False, False)])
def test_timeseries_dataset_collection_load(
    tqdm1: MagicMock, tqdm2: MagicMock, pages: list[DatapointPage], show_progress: bool, skip_data: bool
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
    mocked.service.get_dataset_for_time_interval.side_effect = [Promise.resolve(page) for page in pages]
    # the interval doesn't actually matter here, since we mock the response
    interval = TimeInterval(datetime.now(), datetime.now() + timedelta(days=1))
    dataset = mocked.collection.load(interval, show_progress=show_progress, skip_data=skip_data)
    _assert_datapoints_match(dataset, pages)

    if show_progress:
        expected_updates = len(pages) if len(pages) > 1 else 0
        assert progress_bar.update.call_count == expected_updates


@patch("tilebox.datasets.sync.pagination.tqdm")
@settings(deadline=1000, max_examples=3)  # increase deadline to 1s to not timeout because of the progress bar
@given(pages=paginated_datapoint_for_interval_responses())
@pytest.mark.parametrize("show_progress", [True, False])
def test_timeseries_dataset_collection_find_interval(
    tqdm: MagicMock, pages: list[DatapointPage], show_progress: bool
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
    mocked.service.get_dataset_for_datapoint_interval.side_effect = [Promise.resolve(page) for page in pages]
    # the interval doesn't actually matter here, since we mock the response
    dataset = mocked.collection._find_interval((uuid4(), uuid4()), show_progress=show_progress)
    _assert_datapoints_match(dataset, pages)

    if show_progress:
        expected_updates = len(pages) if len(pages) > 1 else 0
        assert progress_bar.update.call_count == expected_updates


def _assert_datapoints_match(dataset: xr.Dataset, pages: list[DatapointPage]) -> None:
    """Assert that the datapoints in the dataset match the given list of protobuf datapoints."""
    assert isinstance(dataset, xr.Dataset)

    datapoints = []
    for page in pages:
        datapoints.extend(page.meta)

    if len(datapoints) > 0:
        assert len(dataset.time) == len(datapoints)
    for i, meta in enumerate(datapoints):
        datapoint = dataset.isel(time=i)
        assert timestamp_to_datetime(meta.event_time) == _convert_to_datetime(datapoint.coords["time"].item())
        assert timestamp_to_datetime(meta.ingestion_time) == _convert_to_datetime(
            datapoint.coords["ingestion_time"].item()
        )
        assert meta.id == datapoint.coords["id"]


class MockCollectionService(CollectionServiceStub):
    """A mock implementation of the gRPC collection service, that stores collections in memory as a dict."""

    def __init__(self) -> None:
        self.collections: dict[str, CollectionInfoMessage] = {}

    def CreateCollection(self, req: CreateCollectionRequest) -> CollectionInfoMessage:  # noqa: N802
        collection = CollectionInfoMessage(
            collection=CollectionMessage(id=uuid_to_uuid_message(uuid4()), name=req.name), availability=None, count=None
        )
        self.collections[req.name] = collection
        return collection

    def GetCollectionByName(self, req: GetCollectionByNameRequest) -> CollectionInfoMessage:  # noqa: N802
        if req.collection_name in self.collections:
            return self.collections[req.collection_name]
        raise NotFoundError(f"Collection {req.collection_name} not found")

    def ListCollections(self, req: ListCollectionsRequest) -> CollectionInfosMessage:  # noqa: N802
        _ = req
        return CollectionInfosMessage(data=list(self.collections.values()))


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
        dataset_client, _ = _mocked_dataset()
        dataset_client._service = TileboxDatasetService(
            MagicMock(), MockCollectionService(), MagicMock(), MagicMock()
        )  # mock the gRPC service
        self.dataset_client = dataset_client
        self.count_collections = 0

    inserted_collections: Bundle[TimeseriesCollection] = Bundle("collections")

    @rule(target=inserted_collections, collection=collection_infos())
    def get_or_create_collection_enfore_create(self, collection: CollectionInfo) -> TimeseriesCollection:
        collections = self.dataset_client.collections()
        assume(collection.collection.name not in collections)

        self.count_collections += 1
        return self.dataset_client.get_or_create_collection(collection.collection.name)

    @rule(collection=inserted_collections)
    def get_or_create_collection_enfore_get(self, collection: TimeseriesCollection) -> None:
        got = self.dataset_client.get_or_create_collection(collection.name)
        assert got.info() == collection.info()

    @rule(target=inserted_collections, collection=collection_infos())
    def create_collection(self, collection: CollectionInfo) -> TimeseriesCollection:
        collections = self.dataset_client.collections()
        assume(collection.collection.name not in collections)

        self.count_collections += 1
        return self.dataset_client.create_collection(collection.collection.name)

    @rule(collection=inserted_collections)
    def get_collection(self, collection: TimeseriesCollection) -> None:
        got = self.dataset_client.collection(collection.name)
        assert got.info() == collection.info()

    @invariant()
    def list_collections(self) -> None:
        collections = self.dataset_client.collections()
        assert len(collections) == self.count_collections


# make pytest pick up the test cases from the state machine
TestCollectionCRUDOperations = CollectionCRUDOperations.TestCase
