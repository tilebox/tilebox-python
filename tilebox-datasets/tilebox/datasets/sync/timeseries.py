from collections.abc import Iterator
from functools import partial
from warnings import warn

import xarray as xr

from _tilebox.grpc.error import ArgumentError, NotFoundError
from _tilebox.grpc.producer_consumer import concurrent_producer_consumer
from tilebox.datasets.data.collection import CollectionInfo
from tilebox.datasets.data.datapoint import DatapointInterval, DatapointPage
from tilebox.datasets.data.datasets import Dataset
from tilebox.datasets.data.pagination import Pagination
from tilebox.datasets.data.time_interval import TimeInterval, TimeIntervalLike
from tilebox.datasets.progress import ProgressCallback
from tilebox.datasets.protobuf_xarray import TimeseriesToXarrayConverter
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.sync.pagination import (
    paginated_request,
    with_progressbar,
    with_time_progress_callback,
    with_time_progressbar,
)

# allow private member access: we allow it here because we want to make as much private as possible so that we can
# minimize the publicly facing API (which allows us to change internals later, and also limits to auto-completion)
# ruff: noqa: SLF001


class TimeseriesDataset:
    """A client for a timeseries dataset."""

    def __init__(
        self,
        service: TileboxDatasetService,
        dataset: Dataset,
    ) -> None:
        self._service = service
        self.name = dataset.name
        self._dataset = dataset

    def collections(
        self, availability: bool | None = None, count: bool | None = None
    ) -> dict[str, "TimeseriesCollection"]:
        """
        List the available collections in this dataset.

        Args:
            availability: Unused.
            count: Unused.

        Returns:
            A mapping from collection names to collections.
        """
        if availability is not None:
            warn("availability is unused", DeprecationWarning, stacklevel=2)
        if count is not None:
            warn("count is unused", DeprecationWarning, stacklevel=2)

        collections = self._service.get_collections(self._dataset.id, True, True).get()

        dataset_collections = {}
        for collection in collections:
            remote_collection = TimeseriesCollection(self, collection.collection.name)
            remote_collection._info = collection
            dataset_collections[collection.collection.name] = remote_collection

        return dataset_collections

    def get_or_create_collection(self, name: str) -> "TimeseriesCollection":
        """Get a collection by its name, or create it if it doesn't exist.

        Args:
            name: The name of the collection to get or create.

        Returns:
            The collection with the given name.
        """
        try:
            collection = self.collection(name)
        except NotFoundError:
            return self.create_collection(name)
        return collection

    def create_collection(self, name: str) -> "TimeseriesCollection":
        """Create a new collection in this dataset.

        Args:
            name: The name of the collection to create.

        Returns:
            The created collection.
        """
        info = self._service.create_collection(self._dataset.id, name).get()

        collection = TimeseriesCollection(self, info.collection.name)
        collection._info = info
        return collection

    def collection(self, name: str) -> "TimeseriesCollection":
        """Get a collection by its name.

        Args:
            collection: The name of the collection to get.

        Returns:
            The collection with the given name.
        """
        try:
            info = self._service.get_collection_by_name(self._dataset.id, name, True, True).get()
        except NotFoundError:
            raise NotFoundError(f"No such collection {name}") from None

        collection = TimeseriesCollection(self, name)
        collection._info = info
        return collection

    def __repr__(self) -> str:
        return f"{self.name} [Timeseries Dataset]: {self._dataset.summary}"


class TimeseriesCollection:
    """A client for a datapoint collection in a specific timeseries dataset."""

    def __init__(
        self,
        dataset: TimeseriesDataset,
        collection_name: str,
    ) -> None:
        self._dataset = dataset
        self.name = collection_name
        self._info: CollectionInfo

    def __repr__(self) -> str:
        """Human readable representation of the collection."""
        return repr(self._info)

    def info(self, availability: bool | None = None, count: bool | None = None) -> CollectionInfo:
        """
        Return metadata about the datapoints in this collection.

        Args:
            availability: Unused.
            count: Unused.

        Returns:
            collection info for the current collection
        """
        if availability is not None:
            warn("availability is unused", DeprecationWarning, stacklevel=2)
        if count is not None:
            warn("count is unused", DeprecationWarning, stacklevel=2)

        return self._info

    def find(self, datapoint_id: str, skip_data: bool = False) -> xr.Dataset:
        """
        Find a specific datapoint in this collection by its id.

        Args:
            datapoint_id: The id of the datapoint to find
            skip_data: Whether to skip the actual data of the datapoint. If True, only datapoint metadata is returned.

        Returns:
            The datapoint as an xarray dataset
        """
        try:
            datapoint = self._dataset._service.get_datapoint_by_id(
                self._info.collection.id, datapoint_id, skip_data
            ).get()
        except ArgumentError:
            raise ValueError(f"Invalid datapoint id: {datapoint_id} is not a valid UUID") from None
        except NotFoundError:
            raise NotFoundError(f"No such datapoint {datapoint_id}") from None

        converter = TimeseriesToXarrayConverter(initial_capacity=1)
        converter.convert(datapoint)
        return converter.finalize().isel(time=0)

    def _find_interval(
        self,
        datapoint_id_interval: tuple[str, str],
        end_inclusive: bool = True,
        *,
        skip_data: bool = False,
        show_progress: bool = False,
    ) -> xr.Dataset:
        """
        Find a range of datapoints in this collection in an interval specified as datapoint ids.

        Args:
            datapoint_id_interval: tuple of two datapoint ids specifying the interval: [start_id, end_id]
            end_inclusive: Flag indicating whether the datapoint with the given end_id should be included in the
                result or not.
            skip_data: Whether to skip the actual data of the datapoint. If True, only datapoint metadata is returned.
            show_progress: Whether to show a progress bar while loading the data.

        Returns:
            The datapoints in the given interval as an xarray dataset
        """
        start_id, end_id = datapoint_id_interval

        datapoint_interval = DatapointInterval(
            start_id=start_id,
            end_id=end_id,
            start_exclusive=False,
            end_inclusive=end_inclusive,
        )

        def request(page: Pagination) -> DatapointPage:
            return self._dataset._service.get_dataset_for_datapoint_interval(
                self._info.collection.id, datapoint_interval, skip_data, False, page
            ).get()

        initial_page = Pagination()
        pages = paginated_request(request, initial_page)
        if show_progress:
            pages = with_progressbar(pages, f"Fetching {self._dataset.name}")

        return _convert_to_dataset(pages)

    def load(
        self,
        time_or_interval: TimeIntervalLike,
        *,
        skip_data: bool = False,
        show_progress: bool | ProgressCallback = False,
    ) -> xr.Dataset:
        """
        Load a range of datapoints in this collection in a specified interval.

        The interval can be specified in a number of ways:
        - TimeInterval: interval -> Use the time interval as its given
        - DatetimeScalar: [time, time] -> Construct a TimeInterval with start and end time set to the given value and
            the end time inclusive
        - tuple of two DatetimeScalar: [start, end) -> Construct a TimeInterval with the given start and end time
        - xr.DataArray: [arr[0], arr[-1]] -> Construct a TimeInterval with start and end time set to the first and last
            value in the array and the end time inclusive
        - xr.Dataset: [ds.time[0], ds.time[-1]] -> Construct a TimeInterval with start and end time set to the first
            and last value in the time coordinate of the dataset and the end time inclusive

        Args:
            time_or_interval: The interval argument as described above
            skip_data: Whether to skip the actual data of the datapoint. If True, only datapoint metadata is returned.
            show_progress: Whether to show a progress bar while loading the data

        Returns:
            The datapoints in the given interval as an xarray dataset
        """
        pages = self._iter_pages(time_or_interval, skip_data, show_progress=show_progress)
        return _convert_to_dataset(pages)

    def _iter_pages(
        self,
        time_or_interval: TimeIntervalLike,
        skip_data: bool = False,
        skip_meta: bool = False,
        show_progress: bool | ProgressCallback = False,
        page_size: int | None = None,
    ) -> Iterator[DatapointPage]:
        time_interval = TimeInterval.parse(time_or_interval)

        request = partial(self._load_page, time_interval, skip_data, skip_meta)

        initial_page = Pagination(limit=page_size)
        pages = paginated_request(request, initial_page)

        if callable(show_progress):
            if skip_meta:
                raise ValueError("Progress callback requires datapoint metadata, but skip_meta is True")
            else:
                pages = with_time_progress_callback(pages, time_interval, show_progress)
        elif show_progress:
            message = f"Fetching {self._dataset.name}"
            if skip_meta:  # without metadata we can't estimate progress based on event time (since it is not returned)
                pages = with_progressbar(pages, message)
            else:
                pages = with_time_progressbar(pages, time_interval, message)

        yield from pages

    def _load_page(
        self, time_interval: TimeInterval, skip_data: bool, skip_meta: bool, page: Pagination | None = None
    ) -> DatapointPage:
        return self._dataset._service.get_dataset_for_time_interval(
            self._info.collection.id, time_interval, skip_data, skip_meta, page
        ).get()


def _convert_to_dataset(pages: Iterator[DatapointPage]) -> xr.Dataset:
    """
    Convert an iterator of DatasetIntervals (pages) into a single xarray Dataset

    Parses each incoming page while in parallel already requesting and waiting for the next page from the server.

    Args:
        pages: Iterator of DatasetIntervals (pages) to convert

    Returns:
        The datapoints from the individual pages converted and combined into a single xarray dataset
    """

    converter = TimeseriesToXarrayConverter()
    # lets parse the incoming pages already while we wait for the next page from the server
    # we solve this using a classic producer/consumer with a queue of pages for communication
    # this would also account for the case where the server sends pages faster than we are converting
    # them to xarray
    concurrent_producer_consumer(pages, lambda page: converter.convert_all(page))
    return converter.finalize()
