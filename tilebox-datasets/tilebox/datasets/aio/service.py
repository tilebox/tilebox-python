from uuid import UUID

from grpc.aio import Channel

from _tilebox.grpc.aio.error import with_pythonic_errors
from tilebox.datasets.data.collection import CollectionInfo
from tilebox.datasets.data.datapoint import (
    Datapoint,
    DatapointInterval,
    DatapointPage,
    DeleteDatapointsResponse,
    IngestDatapointsResponse,
)
from tilebox.datasets.data.datasets import Dataset, ListDatasetsResponse
from tilebox.datasets.data.pagination import Pagination
from tilebox.datasets.data.time_interval import TimeInterval
from tilebox.datasets.data.uuid import uuid_to_uuid_message
from tilebox.datasets.datasetsv1 import core_pb2
from tilebox.datasets.datasetsv1.core_pb2 import (
    CreateCollectionRequest,
    GetCollectionByNameRequest,
    GetCollectionsRequest,
    GetDatapointByIdRequest,
    GetDatasetForIntervalRequest,
)
from tilebox.datasets.datasetsv1.tilebox_pb2 import (
    DeleteDatapointsRequest,
    GetDatasetRequest,
    IngestDatapointsRequest,
    ListDatasetsRequest,
)
from tilebox.datasets.datasetsv1.tilebox_pb2_grpc import TileboxServiceStub
from tilebox.datasets.sync.service import _client_info


class TileboxDatasetService:
    def __init__(self, channel: Channel) -> None:
        """
        Typed access to the gRPC endpoints of a timeseries dataset.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self._service = with_pythonic_errors(TileboxServiceStub(channel))

    async def list_datasets(self) -> ListDatasetsResponse:
        """List all datasets and dataset groups."""
        response = await self._service.ListDatasets(ListDatasetsRequest(client_info=_client_info()))
        return ListDatasetsResponse.from_message(response)

    async def get_dataset(self, dataset_id: UUID) -> Dataset:
        """Get a dataset by its id."""
        response = await self._service.GetDataset(GetDatasetRequest(dataset_id=str(dataset_id)))
        return Dataset.from_message(response)

    async def create_collection(self, dataset_id: UUID, name: str) -> CollectionInfo:
        """Create a new collection in a dataset.

        Args:
            dataset_id: The id of the dataset to create the collection in.
            name: The name of the collection to create.

        Returns:
            The created collection info.
        """
        req = CreateCollectionRequest(dataset_id=uuid_to_uuid_message(dataset_id), name=name)
        response = await self._service.CreateCollection(req)
        return CollectionInfo.from_message(response)

    async def get_collections(
        self, dataset_id: UUID, with_availability: bool = True, with_count: bool = False
    ) -> list[CollectionInfo]:
        """List all available collections in this dataset."""
        req = GetCollectionsRequest(
            dataset_id=uuid_to_uuid_message(dataset_id), with_availability=with_availability, with_count=with_count
        )
        response = await self._service.GetCollections(req)
        return [CollectionInfo.from_message(collection) for collection in response.data]

    async def get_collection_by_name(
        self, dataset_id: UUID, collection_name: str, with_availability: bool = True, with_count: bool = False
    ) -> CollectionInfo:
        """Fetch additional metadata about the datapoints in this collection."""
        req = GetCollectionByNameRequest(
            collection_name=collection_name,
            with_availability=with_availability,
            with_count=with_count,
            dataset_id=uuid_to_uuid_message(dataset_id),
        )
        response = await self._service.GetCollectionByName(req)
        return CollectionInfo.from_message(response)

    async def get_datapoint_by_id(self, collection_id: str, datapoint_id: str, skip_data: bool = False) -> Datapoint:
        response = await self._service.GetDatapointByID(
            GetDatapointByIdRequest(collection_id=collection_id, id=datapoint_id, skip_data=skip_data)
        )
        return Datapoint.from_message(response)

    async def get_dataset_for_time_interval(
        self,
        collection_id: str,
        time_interval: TimeInterval,
        skip_data: bool,
        skip_meta: bool,
        page: Pagination | None = None,
    ) -> DatapointPage:
        response = await self._service.GetDatasetForInterval(
            GetDatasetForIntervalRequest(
                collection_id=collection_id,
                time_interval=time_interval.to_message(),
                skip_data=skip_data,
                skip_meta=skip_meta,
                page=page.to_message() if page is not None else None,
            )
        )
        return DatapointPage.from_message(response)

    async def get_dataset_for_datapoint_interval(
        self,
        collection_id: str,
        datapoint_interval: DatapointInterval,
        skip_data: bool,
        skip_meta: bool,
        page: Pagination | None = None,
    ) -> DatapointPage:
        response = await self._service.GetDatasetForInterval(
            GetDatasetForIntervalRequest(
                collection_id=collection_id,
                datapoint_interval=datapoint_interval.to_message(),
                skip_data=skip_data,
                skip_meta=skip_meta,
                page=page.to_message() if page is not None else None,
            )
        )
        return DatapointPage.from_message(response)

    async def ingest_datapoints(
        self, collection_id: UUID, datapoints: DatapointPage, allow_existing: bool
    ) -> IngestDatapointsResponse:
        """Ingest a batch of datapoints into a collection.

        Args:
            collection_id: The UUID of the collection to insert the datapoints into.
            datapoints: The datapoints to insert.
            allow_existing: Whether to allow existing datapoints as part of the request.

        Returns:
            The number of datapoints that were ingested as well as the generated ids for those datapoints.
        """
        response = await self._service.IngestDatapoints(
            IngestDatapointsRequest(
                collection_id=uuid_to_uuid_message(collection_id),
                datapoints=datapoints.to_message(),
                allow_existing=allow_existing,
            )
        )
        return IngestDatapointsResponse.from_message(response)

    async def delete_datapoints(self, collection_id: UUID, datapoints: list[UUID]) -> DeleteDatapointsResponse:
        """Delete a batch of datapoints from a collection.

        Args:
            collection_id: The UUID of the collection to delete the datapoints from.
            datapoints: The datapoints to delete.

        Returns:
            The number of datapoints that were deleted.
        """
        response = await self._service.DeleteDatapoints(
            DeleteDatapointsRequest(
                collection_id=uuid_to_uuid_message(collection_id),
                datapoint_ids=[core_pb2.ID(datapoint.bytes) for datapoint in datapoints],
            )
        )
        return DeleteDatapointsResponse.from_message(response)
