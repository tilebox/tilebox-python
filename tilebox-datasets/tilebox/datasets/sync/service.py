import os
import sys
from importlib.metadata import distributions
from uuid import UUID

from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
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
    def __init__(self, channel: Channel) -> None:
        """
        Typed access to the gRPC endpoints of a timeseries dataset.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self._service = with_pythonic_errors(TileboxServiceStub(channel))

    def list_datasets(self) -> ListDatasetsResponse:
        """List all datasets and dataset groups."""
        response = self._service.ListDatasets(ListDatasetsRequest(client_info=_client_info()))
        return ListDatasetsResponse.from_message(response)

    def get_dataset(self, dataset_id: UUID) -> Dataset:
        """Get a dataset by its id."""
        response = self._service.GetDataset(GetDatasetRequest(dataset_id=str(dataset_id)))
        return Dataset.from_message(response)

    def create_collection(self, dataset_id: UUID, name: str) -> CollectionInfo:
        """Create a new collection in a dataset.

        Args:
            dataset_id: The id of the dataset to create the collection in.
            name: The name of the collection to create.

        Returns:
            The created collection info.
        """
        req = CreateCollectionRequest(dataset_id=uuid_to_uuid_message(dataset_id), name=name)
        response = self._service.CreateCollection(req)
        return CollectionInfo.from_message(response)

    def get_collections(
        self, dataset_id: UUID, with_availability: bool = True, with_count: bool = False
    ) -> list[CollectionInfo]:
        """List all available collections in this dataset."""
        req = GetCollectionsRequest(
            dataset_id=uuid_to_uuid_message(dataset_id), with_availability=with_availability, with_count=with_count
        )
        response = self._service.GetCollections(req)
        return [CollectionInfo.from_message(collection) for collection in response.data]

    def get_collection_by_name(
        self, dataset_id: UUID, collection_name: str, with_availability: bool = True, with_count: bool = False
    ) -> CollectionInfo:
        """Fetch additional metadata about the datapoints in this collection."""
        req = GetCollectionByNameRequest(
            collection_name=collection_name,
            with_availability=with_availability,
            with_count=with_count,
            dataset_id=uuid_to_uuid_message(dataset_id),
        )
        response = self._service.GetCollectionByName(req)
        return CollectionInfo.from_message(response)

    def get_datapoint_by_id(self, collection_id: str, datapoint_id: str, skip_data: bool = False) -> Datapoint:
        response = self._service.GetDatapointByID(
            GetDatapointByIdRequest(collection_id=collection_id, id=datapoint_id, skip_data=skip_data)
        )
        return Datapoint.from_message(response)

    def get_dataset_for_time_interval(
        self,
        collection_id: str,
        time_interval: TimeInterval,
        skip_data: bool,
        skip_meta: bool,
        page: Pagination | None = None,
    ) -> DatapointPage:
        response = self._service.GetDatasetForInterval(
            GetDatasetForIntervalRequest(
                collection_id=collection_id,
                time_interval=time_interval.to_message(),
                skip_data=skip_data,
                skip_meta=skip_meta,
                page=page.to_message() if page is not None else None,
            )
        )
        return DatapointPage.from_message(response)

    def get_dataset_for_datapoint_interval(
        self,
        collection_id: str,
        datapoint_interval: DatapointInterval,
        skip_data: bool,
        skip_meta: bool,
        page: Pagination | None = None,
    ) -> DatapointPage:
        response = self._service.GetDatasetForInterval(
            GetDatasetForIntervalRequest(
                collection_id=collection_id,
                datapoint_interval=datapoint_interval.to_message(),
                skip_data=skip_data,
                skip_meta=skip_meta,
                page=page.to_message() if page is not None else None,
            )
        )
        return DatapointPage.from_message(response)

    def ingest_datapoints(
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
        response = self._service.IngestDatapoints(
            IngestDatapointsRequest(
                collection_id=uuid_to_uuid_message(collection_id),
                datapoints=datapoints.to_message(),
                allow_existing=allow_existing,
            )
        )
        return IngestDatapointsResponse.from_message(response)

    def delete_datapoints(self, collection_id: UUID, datapoints: list[UUID]) -> DeleteDatapointsResponse:
        """Delete a batch of datapoints from a collection.

        Args:
            collection_id: The UUID of the collection to delete the datapoints from.
            datapoints: The datapoints to delete.

        Returns:
            The number of datapoints that were deleted.
        """
        response = self._service.DeleteDatapoints(
            DeleteDatapointsRequest(
                collection_id=uuid_to_uuid_message(collection_id),
                datapoint_ids=[core_pb2.ID(datapoint.bytes) for datapoint in datapoints],
            )
        )
        return DeleteDatapointsResponse.from_message(response)


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
