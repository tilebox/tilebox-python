from collections.abc import Iterator
from functools import partial
from uuid import UUID
from warnings import warn

import xarray as xr

from _tilebox.grpc.error import ArgumentError, NotFoundError
from _tilebox.grpc.producer_consumer import concurrent_producer_consumer
from tilebox.datasets.data.collection import CollectionInfo
from tilebox.datasets.data.data_access import QueryFilters
from tilebox.datasets.data.datapoint import DatapointInterval, DatapointPage, QueryResultPage
from tilebox.datasets.data.datasets import Dataset
from tilebox.datasets.data.pagination import Pagination
from tilebox.datasets.data.time_interval import TimeInterval, TimeIntervalLike
from tilebox.datasets.data.uuid import as_uuid
from tilebox.datasets.message_pool import get_message_type
from tilebox.datasets.progress import ProgressCallback
from tilebox.datasets.protobuf_conversion.protobuf_xarray import MessageToXarrayConverter, TimeseriesToXarrayConverter
from tilebox.datasets.protobuf_conversion.to_protobuf import (
    DatapointIDs,
    IngestionData,
    extract_datapoint_ids,
    marshal_messages,
    to_messages,
)
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
            warn(
                "The availability arg has been deprecated, and will be removed in a future version. "
                "Collection availability information is now always returned instead",
                DeprecationWarning,
                stacklevel=2,
            )
        if count is not None:
            warn(
                "The count arg has been deprecated, and will be removed in a future version. "
                "Collection counts are now always returned instead",
                DeprecationWarning,
                stacklevel=2,
            )

        collections = self._service.get_collections(self._dataset.id, True, True).get()

        return {collection.collection.name: TimeseriesCollection(self, collection) for collection in collections}

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
        return TimeseriesCollection(self, info)

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

        return TimeseriesCollection(self, info)

    def __repr__(self) -> str:
        return f"{self.name} [Timeseries Dataset]: {self._dataset.summary}"


class TimeseriesCollection:
    """A client for a datapoint collection in a specific timeseries dataset."""

    def __init__(self, dataset: TimeseriesDataset, info: CollectionInfo) -> None:
        self._dataset = dataset
        self._use_legacy_api = dataset._dataset.is_legacy_type
        self._collection = info.collection
        self._info: CollectionInfo | None = info

    def __repr__(self) -> str:
        """Human readable representation of the collection."""
        return repr(self._info)

    @property
    def name(self) -> str:
        """The name of the collection."""
        return self._collection.name

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
            warn(
                "The availability arg has been deprecated, and will be removed in a future version. "
                "Collection availability information is now always returned instead",
                DeprecationWarning,
                stacklevel=2,
            )
        if count is not None:
            warn(
                "The count arg has been deprecated, and will be removed in a future version. "
                "Collection counts are now always returned instead",
                DeprecationWarning,
                stacklevel=2,
            )

        if self._info is None:  # only load collection info if it hasn't been loaded yet (or it has been invalidated)
            try:
                self._info = self._dataset._service.get_collection_by_name(
                    self._dataset._dataset.id, self.name, True, True
                ).get()
            except NotFoundError:
                raise NotFoundError(f"No such collection {self.name}") from None

        return self._info

    def find(self, datapoint_id: str | UUID, skip_data: bool = False) -> xr.Dataset:
        """
        Find a specific datapoint in this collection by its id.

        Args:
            datapoint_id: The id of the datapoint to find
            skip_data: Whether to skip the actual data of the datapoint. If True, only datapoint metadata is returned.

        Returns:
            The datapoint as an xarray dataset
        """
        if self._use_legacy_api:  # remove this once all datasets are fully migrated to the new endpoints
            return self._find_legacy(str(datapoint_id), skip_data)

        try:
            datapoint = self._dataset._service.query_by_id(
                [self._collection.id], as_uuid(datapoint_id), skip_data
            ).get()
        except ArgumentError:
            raise ValueError(f"Invalid datapoint id: {datapoint_id} is not a valid UUID") from None
        except NotFoundError:
            raise NotFoundError(f"No such datapoint {datapoint_id}") from None

        message_type = get_message_type(datapoint.type_url)
        data = message_type.FromString(datapoint.value)

        converter = MessageToXarrayConverter(initial_capacity=1)
        converter.convert(data)
        return converter.finalize("time").isel(time=0)

    def _find_legacy(self, datapoint_id: str, skip_data: bool = False) -> xr.Dataset:
        try:
            datapoint = self._dataset._service.get_datapoint_by_id(
                str(self._collection.id), datapoint_id, skip_data
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
        datapoint_id_interval: tuple[str, str] | tuple[UUID, UUID],
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
        if self._use_legacy_api:  # remove this once all datasets are fully migrated to the new endpoints
            return self._find_interval_legacy(
                datapoint_id_interval, end_inclusive, skip_data=skip_data, show_progress=show_progress
            )

        start_id, end_id = datapoint_id_interval

        filters = QueryFilters(
            temporal_interval=DatapointInterval(
                start_id=as_uuid(start_id),
                end_id=as_uuid(end_id),
                start_exclusive=False,
                end_inclusive=end_inclusive,
            )
        )

        def request(page: Pagination) -> QueryResultPage:
            return self._dataset._service.query([self._collection.id], filters, skip_data, page).get()

        initial_page = Pagination()
        pages = paginated_request(request, initial_page)
        if show_progress:
            pages = with_progressbar(pages, f"Fetching {self._dataset.name}")

        return _convert_to_dataset(pages)

    def _find_interval_legacy(
        self,
        datapoint_id_interval: tuple[str, str] | tuple[UUID, UUID],
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
            start_id=as_uuid(start_id),
            end_id=as_uuid(end_id),
            start_exclusive=False,
            end_inclusive=end_inclusive,
        )

        def request(page: Pagination) -> DatapointPage:
            return self._dataset._service.get_dataset_for_datapoint_interval(
                str(self._collection.id), datapoint_interval, skip_data, False, page
            ).get()

        initial_page = Pagination()
        pages = paginated_request(request, initial_page)
        if show_progress:
            pages = with_progressbar(pages, f"Fetching {self._dataset.name}")

        return _convert_to_dataset_legacy(pages)

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
        if self._use_legacy_api:  # remove this once all datasets are fully migrated to the new endpoints
            return self._load_legacy(time_or_interval, skip_data=skip_data, show_progress=show_progress)

        pages = self._iter_pages(time_or_interval, skip_data, show_progress=show_progress)
        return _convert_to_dataset(pages)

    def _iter_pages(
        self,
        time_or_interval: TimeIntervalLike,
        skip_data: bool = False,
        show_progress: bool | ProgressCallback = False,
        page_size: int | None = None,
    ) -> Iterator[QueryResultPage]:
        time_interval = TimeInterval.parse(time_or_interval)
        filters = QueryFilters(temporal_interval=time_interval)

        request = partial(self._load_page, filters, skip_data)

        initial_page = Pagination(limit=page_size)
        pages = paginated_request(request, initial_page)

        if callable(show_progress):
            pages = with_time_progress_callback(pages, time_interval, show_progress)
        elif show_progress:
            message = f"Fetching {self._dataset.name}"
            pages = with_time_progressbar(pages, time_interval, message)

        yield from pages

    def _load_page(self, filters: QueryFilters, skip_data: bool, page: Pagination | None = None) -> QueryResultPage:
        return self._dataset._service.query([self._collection.id], filters, skip_data, page).get()

    def _load_legacy(
        self,
        time_or_interval: TimeIntervalLike,
        *,
        skip_data: bool = False,
        show_progress: bool | ProgressCallback = False,
    ) -> xr.Dataset:
        pages = self._iter_pages_legacy(time_or_interval, skip_data, show_progress=show_progress)
        return _convert_to_dataset_legacy(pages)

    def _iter_pages_legacy(
        self,
        time_or_interval: TimeIntervalLike,
        skip_data: bool = False,
        skip_meta: bool = False,
        show_progress: bool | ProgressCallback = False,
        page_size: int | None = None,
    ) -> Iterator[DatapointPage]:
        time_interval = TimeInterval.parse(time_or_interval)

        request = partial(self._load_page_legacy, time_interval, skip_data, skip_meta)

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

    def _load_page_legacy(
        self, time_interval: TimeInterval, skip_data: bool, skip_meta: bool, page: Pagination | None = None
    ) -> DatapointPage:
        return self._dataset._service.get_dataset_for_time_interval(
            str(self._collection.id), time_interval, skip_data, skip_meta, page
        ).get()

    def ingest(self, data: IngestionData, allow_existing: bool = True) -> list[UUID]:
        """Ingest data into the collection.

        Args:
            data: The data to ingest. Supported data types are:
                - xr.Dataset: Ingest a dataset such as it is returned by the output of `collection.load()`
                - pd.DataFrame: Ingest a pandas DataFrame, mapping the column names to the dataset fields
                - Iterable, dict or nd-array: Ingest any object that can be converted to a pandas DataFrame,
                    equivalent to `ingest(pd.DataFrame(data))`
            allow_existing: Whether to allow existing datapoints. Datapoints will only be overwritten if
                all of their fields are exactly equal to already existing datapoints. Tilebox will never create
                duplicate datapoints, but will raise an error if the datapoint already exists. Setting this to
                `True` will not raise an error and skip the duplicate datapoints instead.

        Returns:
            List of datapoint ids that were ingested.
        """

        if self._use_legacy_api:  # remove this once all datasets are fully migrated to the new endpoints
            raise ValueError("Ingestion is not supported for this dataset. Please create a new dataset.")

        message_type = get_message_type(self._dataset._dataset.type.type_url)
        messages = marshal_messages(
            to_messages(data, message_type, required_fields=["time"], ignore_fields=["id", "ingestion_time"])
        )
        response = self._dataset._service.ingest(self._collection.id, messages, allow_existing).get()
        self._info = None  # invalidate collection info, since we just ingested some data into it
        return response.datapoint_ids

    def delete(self, datapoints: DatapointIDs) -> int:
        """Delete datapoints from the collection.

        Datapoints are identified and deleted by their ids.

        Args:
            datapoints: The datapoints to delete. Supported types are:
                - xr.Dataset: An xarray.Dataset containing an "id" variable/coord consisting of datapoint IDs to delete.
                - pd.DataFrame: A pandas DataFrame containing a "id" column consisting of datapoint IDs to delete.
                - xr.DataArray, np.ndarray, pd.Series, list[UUID]: Array of UUIDs to delete
                - list[str], list[UUID]: List of datapoint IDs to delete

        Returns:
            The number of datapoints that were deleted.

        Raises:
            NotFoundError: If one or more of the datapoints to delete doesn't exist - no datapoints
                will be deleted if any of the requested deletions doesn't exist.
        """
        datapoint_ids = extract_datapoint_ids(datapoints)
        num_deleted = self._dataset._service.delete(self._collection.id, datapoint_ids).get()
        self._info = None  # invalidate collection info, since we just deleted some data from it
        return num_deleted


def _convert_to_dataset(pages: Iterator[QueryResultPage]) -> xr.Dataset:
    """
    Convert an iterator of QueryResultPages into a single xarray Dataset

    Parses each incoming page while in parallel already requesting and waiting for the next page from the server.

    Args:
        pages: Iterator of QueryResultPages to convert

    Returns:
        The datapoints from the individual pages converted and combined into a single xarray dataset
    """
    converter = MessageToXarrayConverter()

    def convert_page(page: QueryResultPage) -> None:
        message_type = get_message_type(page.data.type_url)
        messages = [message_type.FromString(v) for v in page.data.value]
        converter.convert_all(messages)

    # lets parse the incoming pages already while we wait for the next page from the server
    # we solve this using a classic producer/consumer with a queue of pages for communication
    # this would also account for the case where the server sends pages faster than we are converting
    # them to xarray
    concurrent_producer_consumer(pages, convert_page)
    return converter.finalize("time")


def _convert_to_dataset_legacy(pages: Iterator[DatapointPage]) -> xr.Dataset:
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
