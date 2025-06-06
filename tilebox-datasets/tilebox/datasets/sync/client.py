from uuid import UUID

from _tilebox.grpc.channel import open_channel
from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.client import Client as BaseClient
from tilebox.datasets.client import token_from_env
from tilebox.datasets.datasetsv1.collections_pb2_grpc import CollectionServiceStub
from tilebox.datasets.datasetsv1.data_access_pb2_grpc import DataAccessServiceStub
from tilebox.datasets.datasetsv1.data_ingestion_pb2_grpc import DataIngestionServiceStub
from tilebox.datasets.datasetsv1.datasets_pb2_grpc import DatasetServiceStub
from tilebox.datasets.group import Group
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.sync.timeseries import TimeseriesDataset


class Client:
    def __init__(self, *, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        """
        Create a Tilebox datasets client.

        Args:
            url: Tilebox API Url. Defaults to "https://api.tilebox.com".
            token: The API Key to authenticate with. If not set the `TILEBOX_API_KEY` environment variable will be used.
        """
        channel = open_channel(url, token_from_env(url, token))
        dataset_service_stub = with_pythonic_errors(DatasetServiceStub(channel))
        collection_service_stub = with_pythonic_errors(CollectionServiceStub(channel))
        data_access_service_stub = with_pythonic_errors(DataAccessServiceStub(channel))
        data_ingestion_service_stub = with_pythonic_errors(DataIngestionServiceStub(channel))
        service = TileboxDatasetService(
            dataset_service_stub, collection_service_stub, data_access_service_stub, data_ingestion_service_stub
        )
        self._client = BaseClient(service)

    def datasets(self) -> Group:
        return self._client.datasets(TimeseriesDataset).get()

    def dataset(self, slug: str) -> TimeseriesDataset:
        return self._client.dataset(slug, TimeseriesDataset).get()

    def _dataset_by_id(self, dataset_id: str | UUID) -> TimeseriesDataset:
        return self._client._dataset_by_id(dataset_id, TimeseriesDataset).get()  # noqa: SLF001
