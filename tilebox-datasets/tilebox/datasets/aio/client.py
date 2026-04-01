import os
from uuid import UUID

from loguru import logger

from _tilebox.grpc.aio.channel import open_channel
from _tilebox.grpc.aio.error import with_pythonic_errors
from _tilebox.grpc.error import NotFoundError
from _tilebox.grpc.public import _PUBLIC_RPC_METHOD_PREFIX
from tilebox.datasets.aio.dataset import DatasetClient
from tilebox.datasets.client import _TILEBOX_API_KEY_ENV_VAR, _TILEBOX_API_URL, _TILEBOX_DEV_API_URL
from tilebox.datasets.client import Client as BaseClient
from tilebox.datasets.data.datasets import DatasetKind, FieldDict
from tilebox.datasets.datasets.v1.collections_pb2_grpc import CollectionServiceStub
from tilebox.datasets.datasets.v1.data_access_pb2_grpc import DataAccessServiceStub
from tilebox.datasets.datasets.v1.data_ingestion_pb2_grpc import DataIngestionServiceStub
from tilebox.datasets.datasets.v1.datasets_pb2_grpc import DatasetServiceStub
from tilebox.datasets.group import Group
from tilebox.datasets.service import TileboxDatasetService


class Client:
    def __init__(
        self, *, url: str = _TILEBOX_API_URL, token: str | None = None, warn_if_unauthenticated: bool = True
    ) -> None:
        """
        Create a Tilebox datasets client.

        Args:
            url: Tilebox API Url. Defaults to "https://api.tilebox.com".
            token: The API Key to authenticate with. If not set the `TILEBOX_API_KEY` environment variable will be used.
                If no token is provided or found, anonymous open data access will be used.
            warn_if_unauthenticated: Whether to warn if no API key is provided and the client is used with the default
                Tilebox API URL. Defaults to True.
        """
        url = url.removesuffix("/")

        if token is None:
            token = os.environ.get(_TILEBOX_API_KEY_ENV_VAR, None)

        is_tilebox_deployment = url in (_TILEBOX_API_URL, _TILEBOX_DEV_API_URL)
        if token is None and is_tilebox_deployment and warn_if_unauthenticated:
            logger.opt(colors=True).info(
                "<yellow>"
                "No Tilebox API key detected. Using <bold>anonymous open data access</bold> without authentication. "
                "For higher throughput and rate limits, sign up for a free account at https://console.tilebox.com."
                "</yellow>"
            )

        channel = open_channel(
            url,
            token,
            rpc_method_prefix=_PUBLIC_RPC_METHOD_PREFIX if (is_tilebox_deployment and token is None) else None,
        )
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
