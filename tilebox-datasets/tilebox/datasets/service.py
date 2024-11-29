import os
import sys
from importlib.metadata import distributions
from uuid import UUID

from promise import Promise

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
    ClientInfo,
    DeleteDatapointsRequest,
    GetDatasetRequest,
    IngestDatapointsRequest,
    ListDatasetsRequest,
    Package,
)
from tilebox.datasets.datasetsv1.tilebox_pb2_grpc import TileboxServiceStub


class TileboxDatasetService:
    def __init__(self, service_stub: TileboxServiceStub) -> None:
        """
        Typed access to the gRPC endpoints of a timeseries dataset.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self._service = service_stub

    def list_datasets(self) -> Promise[ListDatasetsResponse]:
        """List all datasets and dataset groups."""
        return Promise.resolve(self._service.ListDatasets(ListDatasetsRequest(client_info=_client_info()))).then(
            ListDatasetsResponse.from_message
        )

    def get_dataset_by_id(self, dataset_id: str) -> Promise[Dataset]:
        """Get a dataset by its id."""
        return Promise.resolve(self._service.GetDataset(GetDatasetRequest(id=dataset_id))).then(Dataset.from_message)

    def get_dataset_by_slug(self, slug: str) -> Promise[Dataset]:
        """Get a dataset by its id."""
        return Promise.resolve(self._service.GetDataset(GetDatasetRequest(slug=slug))).then(Dataset.from_message)

    def create_collection(self, dataset_id: UUID, name: str) -> Promise[CollectionInfo]:
        """Create a new collection in a dataset.

        Args:
            dataset_id: The id of the dataset to create the collection in.
            name: The name of the collection to create.

        Returns:
            The created collection info.
        """
        req = CreateCollectionRequest(dataset_id=uuid_to_uuid_message(dataset_id), name=name)
        return Promise.resolve(self._service.CreateCollection(req)).then(CollectionInfo.from_message)

    def get_collections(
        self, dataset_id: UUID, with_availability: bool = True, with_count: bool = False
    ) -> Promise[list[CollectionInfo]]:
        """List all available collections in this dataset."""
        req = GetCollectionsRequest(
            dataset_id=uuid_to_uuid_message(dataset_id), with_availability=with_availability, with_count=with_count
        )
        return Promise.resolve(self._service.GetCollections(req)).then(
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
        return Promise.resolve(self._service.GetCollectionByName(req)).then(
            CollectionInfo.from_message,
        )

    def get_datapoint_by_id(self, collection_id: str, datapoint_id: str, skip_data: bool = False) -> Promise[Datapoint]:
        req = GetDatapointByIdRequest(collection_id=collection_id, id=datapoint_id, skip_data=skip_data)
        return Promise.resolve(self._service.GetDatapointByID(req)).then(
            Datapoint.from_message,
        )

    def get_dataset_for_time_interval(
        self,
        collection_id: str,
        time_interval: TimeInterval,
        skip_data: bool,
        skip_meta: bool,
        page: Pagination | None = None,
    ) -> Promise[DatapointPage]:
        req = GetDatasetForIntervalRequest(
            collection_id=collection_id,
            time_interval=time_interval.to_message(),
            skip_data=skip_data,
            skip_meta=skip_meta,
            page=page.to_message() if page is not None else None,
        )
        return Promise.resolve(self._service.GetDatasetForInterval(req)).then(
            DatapointPage.from_message,
        )

    def get_dataset_for_datapoint_interval(
        self,
        collection_id: str,
        datapoint_interval: DatapointInterval,
        skip_data: bool,
        skip_meta: bool,
        page: Pagination | None = None,
    ) -> Promise[DatapointPage]:
        req = GetDatasetForIntervalRequest(
            collection_id=collection_id,
            datapoint_interval=datapoint_interval.to_message(),
            skip_data=skip_data,
            skip_meta=skip_meta,
            page=page.to_message() if page is not None else None,
        )
        return Promise.resolve(self._service.GetDatasetForInterval(req)).then(
            DatapointPage.from_message,
        )

    def ingest_datapoints(
        self, collection_id: UUID, datapoints: DatapointPage, allow_existing: bool
    ) -> Promise[IngestDatapointsResponse]:
        """Ingest a batch of datapoints into a collection.

        Args:
            collection_id: The UUID of the collection to insert the datapoints into.
            datapoints: The datapoints to insert.
            allow_existing: Whether to allow existing datapoints as part of the request.

        Returns:
            The number of datapoints that were ingested as well as the generated ids for those datapoints.
        """
        req = IngestDatapointsRequest(
            collection_id=uuid_to_uuid_message(collection_id),
            datapoints=datapoints.to_message(),
            allow_existing=allow_existing,
        )
        return Promise.resolve(self._service.IngestDatapoints(req)).then(
            IngestDatapointsResponse.from_message,
        )

    def delete_datapoints(self, collection_id: UUID, datapoints: list[UUID]) -> Promise[DeleteDatapointsResponse]:
        """Delete a batch of datapoints from a collection.

        Args:
            collection_id: The UUID of the collection to delete the datapoints from.
            datapoints: The datapoints to delete.

        Returns:
            The number of datapoints that were deleted.
        """
        req = DeleteDatapointsRequest(
            collection_id=uuid_to_uuid_message(collection_id),
            datapoint_ids=[core_pb2.ID(datapoint.bytes) for datapoint in datapoints],
        )
        return Promise.resolve(self._service.DeleteDatapoints(req)).then(
            DeleteDatapointsResponse.from_message,
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
