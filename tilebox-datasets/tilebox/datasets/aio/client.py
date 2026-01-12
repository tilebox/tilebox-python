from uuid import UUID

from _tilebox.grpc.aio.channel import open_channel
from _tilebox.grpc.aio.error import with_pythonic_errors
from _tilebox.grpc.error import NotFoundError
from tilebox.datasets.aio.dataset import DatasetClient
from tilebox.datasets.client import Client as BaseClient
from tilebox.datasets.client import token_from_env
from tilebox.datasets.data.datasets import DatasetKind, FieldDict
from tilebox.datasets.datasets.v1.collections_pb2_grpc import CollectionServiceStub
from tilebox.datasets.datasets.v1.data_access_pb2_grpc import DataAccessServiceStub
from tilebox.datasets.datasets.v1.data_ingestion_pb2_grpc import DataIngestionServiceStub
from tilebox.datasets.datasets.v1.datasets_pb2_grpc import DatasetServiceStub
from tilebox.datasets.group import Group
from tilebox.datasets.service import TileboxDatasetService


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

    async def create_or_update_dataset(
        self,
        kind: DatasetKind,
        code_name: str,
        fields: list[FieldDict] | None = None,
        *,
        name: str | None = None,
    ) -> DatasetClient:
        """Create a new dataset.

        Args:
            kind: The kind of the dataset.
            code_name: The code name of the dataset.
            fields: The custom fields of the dataset.
            name: The name of the dataset. Defaults to the code name.

        Returns:
            The created dataset.
        """

        try:
            dataset = await self.dataset(code_name)
        except NotFoundError:
            return await self._client.create_dataset(kind, code_name, fields or [], name or code_name, DatasetClient)

        return await self._client.update_dataset(
            kind,
            dataset._dataset.id,  # noqa: SLF001
            fields or [],
            name or dataset._dataset.name,  # noqa: SLF001
            DatasetClient,
        )

    async def datasets(self) -> Group:
        """Fetch all available datasets."""
        return await self._client.datasets(DatasetClient)

    async def dataset(self, slug: str) -> DatasetClient:
        """Get a dataset by its slug, e.g. `open_data.copernicus.sentinel1_sar`.

        Args:
            slug: The slug of the dataset.

        Returns:
            The dataset if it exists.
        """
        return await self._client.dataset(slug, DatasetClient)

    async def _dataset_by_id(self, dataset_id: str | UUID) -> DatasetClient:
        return await self._client._dataset_by_id(dataset_id, DatasetClient)  # noqa: SLF001
