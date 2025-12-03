from uuid import UUID

from _tilebox.grpc.channel import open_channel
from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.client import Client as BaseClient
from tilebox.datasets.client import token_from_env
from tilebox.datasets.data.datasets import DatasetKind, FieldDict
from tilebox.datasets.datasets.v1.collections_pb2_grpc import CollectionServiceStub
from tilebox.datasets.datasets.v1.data_access_pb2_grpc import DataAccessServiceStub
from tilebox.datasets.datasets.v1.data_ingestion_pb2_grpc import DataIngestionServiceStub
from tilebox.datasets.datasets.v1.datasets_pb2_grpc import DatasetServiceStub
from tilebox.datasets.group import Group
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.sync.dataset import DatasetClient


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

    def create_dataset(
        self,
        kind: DatasetKind,
        code_name: str,
        fields: list[FieldDict],
        *,
        name: str | None = None,
        summary: str | None = None,
    ) -> DatasetClient:
        if name is None:
            name = code_name
        if summary is None:
            summary = ""

        return self._client.create_dataset(kind, code_name, fields, name, summary, DatasetClient).get()

    def datasets(self) -> Group:
        return self._client.datasets(DatasetClient).get()

    def dataset(self, slug: str) -> DatasetClient:
        return self._client.dataset(slug, DatasetClient).get()

    def _dataset_by_id(self, dataset_id: str | UUID) -> DatasetClient:
        return self._client._dataset_by_id(dataset_id, DatasetClient).get()  # noqa: SLF001
