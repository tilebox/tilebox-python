import os
import sys
from importlib.metadata import distributions
from uuid import UUID

from promise import Promise

from tilebox.datasets.data.collection import CollectionInfo
from tilebox.datasets.data.data_access import QueryFilters
from tilebox.datasets.data.datapoint import AnyMessage, IngestResponse, QueryResultPage
from tilebox.datasets.data.datasets import Dataset, ListDatasetsResponse
from tilebox.datasets.datasets.v1.collections_pb2 import (
    CreateCollectionRequest,
    DeleteCollectionRequest,
    GetCollectionByNameRequest,
    ListCollectionsRequest,
)
from tilebox.datasets.datasets.v1.collections_pb2_grpc import CollectionServiceStub
from tilebox.datasets.datasets.v1.data_access_pb2 import QueryByIDRequest, QueryRequest
from tilebox.datasets.datasets.v1.data_access_pb2_grpc import DataAccessServiceStub
from tilebox.datasets.datasets.v1.data_ingestion_pb2 import DeleteRequest, IngestRequest
from tilebox.datasets.datasets.v1.data_ingestion_pb2_grpc import DataIngestionServiceStub
from tilebox.datasets.datasets.v1.datasets_pb2 import ClientInfo, GetDatasetRequest, ListDatasetsRequest, Package
from tilebox.datasets.datasets.v1.datasets_pb2_grpc import DatasetServiceStub
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.tilebox.v1 import id_pb2
from tilebox.datasets.uuid import must_uuid_to_uuid_message, uuid_to_uuid_message


class TileboxDatasetService:
    def __init__(
        self,
        dataset_service_stub: DatasetServiceStub,
        collection_service_stub: CollectionServiceStub,
        data_access_service_stub: DataAccessServiceStub,
        data_ingestion_service_stub: DataIngestionServiceStub,
    ) -> None:
        """
        Typed access to the gRPC endpoints of a timeseries dataset.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self._dataset_service = dataset_service_stub
        self._collection_service = collection_service_stub
        self._data_access_service = data_access_service_stub
        self._data_ingestion_service = data_ingestion_service_stub

    def list_datasets(self) -> Promise[ListDatasetsResponse]:
        """List all datasets and dataset groups."""
        return Promise.resolve(
            self._dataset_service.ListDatasets(ListDatasetsRequest(client_info=_client_info()))
        ).then(ListDatasetsResponse.from_message)

    def get_dataset_by_id(self, dataset_id: UUID) -> Promise[Dataset]:
        """Get a dataset by its id."""
        return Promise.resolve(
            self._dataset_service.GetDataset(GetDatasetRequest(id=uuid_to_uuid_message(dataset_id)))
        ).then(Dataset.from_message)

    def get_dataset_by_slug(self, slug: str) -> Promise[Dataset]:
        """Get a dataset by its id."""
        return Promise.resolve(self._dataset_service.GetDataset(GetDatasetRequest(slug=slug))).then(
            Dataset.from_message
        )

    def create_collection(self, dataset_id: UUID, name: str) -> Promise[CollectionInfo]:
        """Create a new collection in a dataset.

        Args:
            dataset_id: The id of the dataset to create the collection in.
            name: The name of the collection to create.

        Returns:
            The created collection info.
        """
        req = CreateCollectionRequest(dataset_id=uuid_to_uuid_message(dataset_id), name=name)
        return Promise.resolve(self._collection_service.CreateCollection(req)).then(CollectionInfo.from_message)

    def delete_collection(self, dataset_id: UUID, collection_id: UUID) -> Promise[None]:
        """Delete a collection in a dataset by id.

        Args:
            dataset_id: The id of the dataset to delete the collection from.
            collection_id: The id of the collection to delete.
        """
        req = DeleteCollectionRequest(
            dataset_id=uuid_to_uuid_message(dataset_id), collection_id=uuid_to_uuid_message(collection_id)
        )
        return Promise.resolve(self._collection_service.DeleteCollection(req))

    def get_collections(
        self, dataset_id: UUID, with_availability: bool = True, with_count: bool = False
    ) -> Promise[list[CollectionInfo]]:
        """List all available collections in this dataset."""
        req = ListCollectionsRequest(
            dataset_id=uuid_to_uuid_message(dataset_id), with_availability=with_availability, with_count=with_count
        )
        return Promise.resolve(self._collection_service.ListCollections(req)).then(
            lambda response: [CollectionInfo.from_message(collection) for collection in response.data],
        )

    def get_collection_by_name(
        self, dataset_id: UUID, collection_name: str, with_availability: bool = True, with_count: bool = False
    ) -> Promise[CollectionInfo]:
        """Fetch additional metadata about the datapoints in this collection."""
        req = GetCollectionByNameRequest(
            collection_name=collection_name,
            with_availability=with_availability,
            with_count=with_count,
            dataset_id=uuid_to_uuid_message(dataset_id),
        )
        return Promise.resolve(self._collection_service.GetCollectionByName(req)).then(
            CollectionInfo.from_message,
        )

    def query_by_id(self, collection_ids: list[UUID], datapoint_id: UUID, skip_data: bool) -> Promise[AnyMessage]:
        req = QueryByIDRequest(
            collection_ids=list(map(must_uuid_to_uuid_message, collection_ids)),
            id=must_uuid_to_uuid_message(datapoint_id),
            skip_data=skip_data,
        )
        return Promise.resolve(self._data_access_service.QueryByID(req)).then(AnyMessage.from_message)

    def query(
        self,
        collection_ids: list[UUID],
        filters: QueryFilters,
        skip_data: bool,
        page: Pagination | None = None,
    ) -> Promise[QueryResultPage]:
        req = QueryRequest(
            collection_ids=list(map(must_uuid_to_uuid_message, collection_ids)),
            filters=filters.to_message(),
            page=page.to_message() if page is not None else None,
            skip_data=skip_data,
        )
        return Promise.resolve(self._data_access_service.Query(req)).then(QueryResultPage.from_message)

    def ingest(self, collection_id: UUID, values: list[bytes], allow_existing: bool) -> Promise[IngestResponse]:
        """Ingest a batch of datapoints into a collection.

        Args:
            collection_id: The UUID of the collection to insert the datapoints into.
            datapoints: The datapoints to insert.
            allow_existing: Whether to allow existing datapoints as part of the request.

        Returns:
            The number of datapoints that were ingested as well as the generated ids for those datapoints.
        """
        req = IngestRequest(
            collection_id=uuid_to_uuid_message(collection_id),
            values=values,
            allow_existing=allow_existing,
        )
        return Promise.resolve(self._data_ingestion_service.Ingest(req)).then(
            IngestResponse.from_message,
        )

    def delete(self, collection_id: UUID, datapoints: list[UUID]) -> Promise[int]:
        """Delete a batch of datapoints from a collection.

        Args:
            collection_id: The UUID of the collection to delete the datapoints from.
            datapoints: The datapoints to delete.

        Returns:
            The number of datapoints that were deleted.
        """
        req = DeleteRequest(
            collection_id=uuid_to_uuid_message(collection_id),
            datapoint_ids=[id_pb2.ID(uuid=datapoint.bytes) for datapoint in datapoints],
        )
        return Promise.resolve(self._data_ingestion_service.Delete(req)).then(
            lambda response: response.num_deleted,
        )


def _client_info() -> ClientInfo:
    tilebox_packages = sorted([pkg for pkg in distributions() if "tilebox" in pkg.name], key=lambda pkg: pkg.name)
    return ClientInfo(
        name="Python",
        environment=_environment_info(),
        packages=[Package(name=pkg.name, version=pkg.version) for pkg in tilebox_packages],
    )


def _environment_info() -> str:
    python_version = sys.version.split(" ")[0]
    try:
        shell = str(get_ipython())  # type: ignore[name-defined]
    except NameError:
        return f"Python {python_version}"  # Probably standard Python interpreter

    if "ZMQInteractiveShell" in shell:
        if "DATALORE_USER" in os.environ:
            return f"Jetbrains Datalore using python {python_version}"
        return f"JupyterLab using python {python_version}"
    if "TerminalInteractiveShell" in shell:
        return f"Terminal IPython using python {python_version}"
    if "google" in shell:
        return f"Google Colab using python {python_version}"

    return f"Unknown IPython using python {python_version}"
