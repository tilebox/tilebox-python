from collections.abc import AsyncIterator
from functools import partial
from typing import cast
from uuid import UUID
from warnings import warn

import xarray as xr
from tqdm.auto import tqdm

from _tilebox.grpc.aio.pagination import Pagination as PaginationProtocol
from _tilebox.grpc.aio.pagination import paginated_request
from _tilebox.grpc.aio.producer_consumer import async_producer_consumer
from _tilebox.grpc.error import ArgumentError, NotFoundError
from tilebox.datasets.aio.pagination import with_progressbar, with_time_progress_callback, with_time_progressbar
from tilebox.datasets.data.collection import CollectionInfo
from tilebox.datasets.data.data_access import QueryFilters, SpatialFilter, SpatialFilterLike
from tilebox.datasets.data.datapoint import QueryResultPage
from tilebox.datasets.data.datasets import Dataset
from tilebox.datasets.message_pool import get_message_type
from tilebox.datasets.progress import ProgressCallback
from tilebox.datasets.protobuf_conversion.protobuf_xarray import MessageToXarrayConverter
from tilebox.datasets.protobuf_conversion.to_protobuf import (
    DatapointIDs,
    IngestionData,
    extract_datapoint_ids,
    marshal_messages,
    to_messages,
)
from tilebox.datasets.query.id_interval import IDInterval, IDIntervalLike
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.query.time_interval import TimeInterval, TimeIntervalLike
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.uuid import as_uuid

# allow private member access: we allow it here because we want to make as much private as possible so that we can
# minimize the publicly facing API (which allows us to change internals later, and also limits to auto-completion)
# ruff: noqa: SLF001


class DatasetClient:
    """A client for a timeseries dataset."""

    def __init__(
        self,
        service: TileboxDatasetService,
        dataset: Dataset,
    ) -> None:
        self._service = service
        self.name = dataset.name
        self._dataset = dataset

    async def collections(
        self, availability: bool | None = None, count: bool | None = None
    ) -> dict[str, "CollectionClient"]:
        """
        List the available collections in a dataset.

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

        collections = await self._service.get_collections(self._dataset.id, True, True)

        return {collection.collection.name: CollectionClient(self, collection) for collection in collections}

    async def get_or_create_collection(self, name: str) -> "CollectionClient":
        """Get a collection by its name, or create it if it doesn't exist.

        Args:
            name: The name of the collection to get or create.

        Returns:
            The collection with the given name.
        """
        try:
            collection = await self.collection(name)
        except NotFoundError:
            return await self.create_collection(name)
        return collection

    async def create_collection(self, name: str) -> "CollectionClient":
        """Create a new collection in this dataset.

        Args:
            name: The name of the collection to create.

        Returns:
            The created collection.
        """
        info = await self._service.create_collection(self._dataset.id, name)
        return CollectionClient(self, info)

    async def collection(self, name: str) -> "CollectionClient":
        """Get a collection by its name.

        Args:
            collection: The name of the collection to get.

        Returns:
            The collection with the given name.
        """
        try:
            info = await self._service.get_collection_by_name(self._dataset.id, name, True, True)
        except NotFoundError:
            raise NotFoundError(f"No such collection {name}") from None

        return CollectionClient(self, info)

    async def delete_collection(self, collection: "str | UUID | CollectionClient") -> None:
        """Delete a collection.

        Args:
            collection: The collection to delete or a collection name or a collection id.
        """
        if isinstance(collection, CollectionClient):
            collection_id = collection._collection.id
        elif isinstance(collection, UUID):
            collection_id = collection
        else:  # str
            collection_id = (await self.collection(collection))._collection.id

        await self._service.delete_collection(self._dataset.id, collection_id)

    def __repr__(self) -> str:
        return f"{self.name} [Timeseries Dataset]: {self._dataset.summary}"


# always ingest / delete in batches, to avoid timeout issues for very large datasets
_INGEST_CHUNK_SIZE = 8192
_DELETE_CHUNK_SIZE = 8192


class CollectionClient:
    """A client for a datapoint collection in a specific timeseries dataset."""

    def __init__(
        self,
        dataset: DatasetClient,
        info: CollectionInfo,
    ) -> None:
        self._dataset = dataset
        self._collection = info.collection
        self._info: CollectionInfo | None = info

    def __repr__(self) -> str:
        """Human readable representation of the collection."""
        return repr(self._info)

    @property
    def name(self) -> str:
        """The name of the collection."""
        return self._collection.name

    async def info(self, availability: bool | None = None, count: bool | None = None) -> CollectionInfo:
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
                self._info = cast(
                    CollectionInfo,
                    await self._dataset._service.get_collection_by_name(
                        self._dataset._dataset.id, self.name, True, True
                    ),
                )
            except NotFoundError:
                raise NotFoundError(f"No such collection {self.name}") from None

        return self._info

    async def find(self, datapoint_id: str | UUID, skip_data: bool = False) -> xr.Dataset:
        """
        Find a specific datapoint in this collection by its id.

        Args:
            datapoint_id: The id of the datapoint to find
            skip_data: Whether to skip the actual data of the datapoint. If True, only datapoint metadata is returned.

        Returns:
            The datapoint as an xarray dataset
        """
        try:
            datapoint = await self._dataset._service.query_by_id(
                [self._collection.id], as_uuid(datapoint_id), skip_data
            )
        except ArgumentError:
            raise ValueError(f"Invalid datapoint id: {datapoint_id} is not a valid UUID") from None
        except NotFoundError:
            raise NotFoundError(f"No such datapoint {datapoint_id}") from None

        message_type = get_message_type(datapoint.type_url)
        data = message_type.FromString(datapoint.value)

        converter = MessageToXarrayConverter(initial_capacity=1)
        converter.convert(data)
        return converter.finalize("time", skip_empty_fields=skip_data).isel(time=0)

    async def _find_interval(
        self,
        datapoint_id_interval: IDIntervalLike,
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
        filters = QueryFilters(temporal_extent=IDInterval.parse(datapoint_id_interval, end_inclusive=end_inclusive))

        async def request(page: PaginationProtocol) -> QueryResultPage:
            query_page = Pagination(page.limit, page.starting_after)
            return await self._dataset._service.query([self._collection.id], filters, skip_data, query_page)

        initial_page = Pagination()
        pages = paginated_request(request, initial_page)
        if show_progress:
            pages = with_progressbar(pages, f"Fetching {self._dataset.name}")

        return await _convert_to_dataset(pages, skip_empty_fields=skip_data)

    async def load(
        self,
        temporal_extent: TimeIntervalLike,
        *,
        skip_data: bool = False,
        show_progress: bool | ProgressCallback = False,
    ) -> xr.Dataset:
        """
        Load a range of datapoints in this collection for a specified temporal_extent.

        An alias for query() without a spatial extent.

        Args:
            temporal_extent: The temporal extent to load data for.
                Can be specified in a number of ways:
                - TimeInterval: interval -> Use the time interval as its given
                - DatetimeScalar: [time, time] -> Construct a TimeInterval with start and end time set to the given
                    value and the end time inclusive
                - tuple of two DatetimeScalar: [start, end) -> Construct a TimeInterval with the given start and
                    end time
                - xr.DataArray: [arr[0], arr[-1]] -> Construct a TimeInterval with start and end time set to the
                    first and last value in the array and the end time inclusive
                - xr.Dataset: [ds.time[0], ds.time[-1]] -> Construct a TimeInterval with start and end time set to
                    the first and last value in the time coordinate of the dataset and the end time inclusive
            skip_data: Whether to skip the actual data of the datapoint. If True, only datapoint metadata is returned.
            show_progress: Whether to show a progress bar while loading the data.
                If a callable is specified it is used as callback to report progress percentages.

        Returns:
            Matching datapoints in the given temporal extent as an xarray dataset
        """
        warn(
            "collection.load(interval) is deprecated. Please use collection.query(temporal_extent=interval) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        return await self.query(temporal_extent=temporal_extent, skip_data=skip_data, show_progress=show_progress)

    async def query(
        self,
        *,
        temporal_extent: TimeIntervalLike,
        spatial_extent: SpatialFilterLike | None = None,
        skip_data: bool = False,
        show_progress: bool | ProgressCallback = False,
    ) -> xr.Dataset:
        """
        Query datapoints in this collection in a specified temporal extent and an optional spatial extent.

        Args:
            temporal_extent: The temporal extent to query data for. (Required)
                Can be specified in a number of ways:
                - TimeInterval: interval -> Use the time interval as its given
                - DatetimeScalar: [time, time] -> Construct a TimeInterval with start and end time set to the given
                    value and the end time inclusive
                - tuple of two DatetimeScalar: [start, end) -> Construct a TimeInterval with the given start and
                    end time
                - xr.DataArray: [arr[0], arr[-1]] -> Construct a TimeInterval with start and end time set to the
                    first and last value in the array and the end time inclusive
                - xr.Dataset: [ds.time[0], ds.time[-1]] -> Construct a TimeInterval with start and end time set to
                    the first and last value in the time coordinate of the dataset and the end time inclusive
            spatial_extent: The spatial extent to query data in. (Optional)
                Expected to be either a shapely geometry, or a dict with the following keys:
                - geometry: The geometry to query by. Must be a shapely.Polygon, shapely.MultiPolygon or shapely.Point.
                - mode: The spatial filter mode to use. Can be one of "intersects" or "contains".
                    Defaults to "intersects".
                - coordinate_system: The coordinate system to use for performing geometry calculations. Can be one
                    of "cartesian" or "spherical".
                Only supported for spatiotemporal datasets. Will raise an error if used for other dataset types.
                All datapoints whose geometry intersects the given spatial extent will be returned.
            skip_data: Whether to skip the actual data of the datapoint. If True, only datapoint metadata is returned.
            show_progress: Whether to show a progress bar while loading the data.
                If a callable is specified it is used as callback to report progress percentages.

        Returns:
            Matching datapoints in the given temporal and spatial extent as an xarray dataset
        """
        if temporal_extent is None:
            raise ValueError("A temporal_extent for your query must be specified")

        pages = self._iter_pages(temporal_extent, spatial_extent, skip_data, show_progress=show_progress)
        return await _convert_to_dataset(pages, skip_empty_fields=skip_data)

    async def _iter_pages(
        self,
        temporal_extent: TimeIntervalLike,
        spatial_extent: SpatialFilterLike | None = None,
        skip_data: bool = False,
        show_progress: bool | ProgressCallback = False,
        page_size: int | None = None,
    ) -> AsyncIterator[QueryResultPage]:
        time_interval = TimeInterval.parse(temporal_extent)
        filters = QueryFilters(time_interval, SpatialFilter.parse(spatial_extent) if spatial_extent else None)

        request = partial(self._query_page, filters, skip_data)

        initial_page = Pagination(limit=page_size)
        pages = paginated_request(request, initial_page)

        if callable(show_progress):
            pages = with_time_progress_callback(pages, time_interval, show_progress)
        elif show_progress:
            message = f"Fetching {self._dataset.name}"
            pages = with_time_progressbar(pages, time_interval, message)

        async for page in pages:
            yield page

    async def _query_page(
        self, filters: QueryFilters, skip_data: bool, page: PaginationProtocol | None = None
    ) -> QueryResultPage:
        query_page = Pagination(page.limit, page.starting_after) if page else Pagination()
        return await self._dataset._service.query([self._collection.id], filters, skip_data, query_page)

    async def ingest(
        self,
        data: IngestionData,
        allow_existing: bool = True,
        *,
        show_progress: bool | ProgressCallback = False,
    ) -> list[UUID]:
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
            show_progress: Whether to show a progress bar while ingestion a large number of datapoints.
                If a callable is specified it is used as callback to report progress percentages.

        Returns:
            List of datapoint ids that were ingested.
        """
        message_type = get_message_type(self._dataset._dataset.type.type_url)
        messages = marshal_messages(
            to_messages(data, message_type, required_fields=["time"], ignore_fields=["id", "ingestion_time"])
        )

        disable_progress_bar = callable(show_progress) or (not show_progress)

        ingested_ids = []
        with tqdm(
            total=len(messages),
            desc=f"Ingesting into {self._dataset.name}",
            unit="datapoints",
            disable=disable_progress_bar,
        ) as progress_bar:
            for chunk_start in range(0, len(messages), _INGEST_CHUNK_SIZE):
                chunk = messages[chunk_start : chunk_start + _INGEST_CHUNK_SIZE]
                response = await self._dataset._service.ingest(self._collection.id, chunk, allow_existing)
                ingested_ids.extend(response.datapoint_ids)

                progress_bar.update(len(chunk))
                if callable(show_progress):
                    show_progress(len(ingested_ids) / len(messages))
                self._info = None  # invalidate collection info, since we just ingested some data into it
        return ingested_ids

    async def delete(self, datapoints: DatapointIDs, *, show_progress: bool | ProgressCallback = False) -> int:
        """Delete datapoints from the collection.

        Datapoints are identified and deleted by their ids.

        Args:
            datapoints: The datapoints to delete. Supported types are:
                - xr.Dataset: An xarray.Dataset containing an "id" variable/coord consisting of datapoint IDs to delete.
                - pd.DataFrame: A pandas DataFrame containing a "id" column consisting of datapoint IDs to delete.
                - xr.DataArray, np.ndarray, pd.Series, list[UUID]: Array of UUIDs to delete
                - list[str], list[UUID]: List of datapoint IDs to delete
            show_progress: Whether to show a progress bar when deleting a large number of datapoints.
                If a callable is specified it is used as callback to report progress percentages.

        Returns:
            The number of datapoints that were deleted.

        Raises:
            NotFoundError: If one or more of the datapoints to delete doesn't exist - no datapoints
                will be deleted if any of the requested deletions doesn't exist.
        """
        datapoint_ids = extract_datapoint_ids(datapoints)
        num_deleted = 0

        disable_progress_bar = callable(show_progress) or (not show_progress)

        with tqdm(
            total=len(datapoint_ids),
            desc=f"Deleting from {self._dataset.name}",
            unit="datapoints",
            disable=disable_progress_bar,
        ) as progress_bar:
            for chunk_start in range(0, len(datapoint_ids), _DELETE_CHUNK_SIZE):
                chunk = datapoint_ids[chunk_start : chunk_start + _DELETE_CHUNK_SIZE]
                num_deleted += await self._dataset._service.delete(self._collection.id, chunk)

                progress_bar.update(len(chunk))
                if callable(show_progress):
                    show_progress(num_deleted / len(datapoint_ids))
                self._info = None  # invalidate collection info, since we just deleted some data from it
        return num_deleted


async def _convert_to_dataset(pages: AsyncIterator[QueryResultPage], skip_empty_fields: bool = False) -> xr.Dataset:
    """
    Convert an async iterator of QueryResultPages into a single xarray Dataset

    Parses each incoming page while in parallel already requesting and waiting for the next page from the server.

    Args:
        pages: Async iterator of QueryResultPages to convert
        skip_empty_fields: Whether to omit fields from the output dataset in case no values are set

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
    await async_producer_consumer(pages, convert_page)
    return converter.finalize("time", skip_empty_fields=skip_empty_fields)
