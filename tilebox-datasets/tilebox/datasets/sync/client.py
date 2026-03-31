import os
from uuid import UUID

from loguru import logger

from _tilebox.grpc.channel import open_channel
from _tilebox.grpc.error import NotFoundError, with_pythonic_errors
from tilebox.datasets.client import _TILEBOX_API_KEY_ENV_VAR, _TILEBOX_API_URL
from tilebox.datasets.client import Client as BaseClient
from tilebox.datasets.data.datasets import DatasetKind, FieldDict
from tilebox.datasets.datasets.v1.collections_pb2_grpc import CollectionServiceStub
from tilebox.datasets.datasets.v1.data_access_pb2_grpc import DataAccessServiceStub
from tilebox.datasets.datasets.v1.data_ingestion_pb2_grpc import DataIngestionServiceStub
from tilebox.datasets.datasets.v1.datasets_pb2_grpc import DatasetServiceStub
from tilebox.datasets.group import Group
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.sync.dataset import DatasetClient


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
        if token is None:
            token = os.environ.get(_TILEBOX_API_KEY_ENV_VAR, None)

        if token is None and url == _TILEBOX_API_URL and warn_if_unauthenticated:
            logger.opt(colors=True).info(
                "<yellow>"
                "No Tilebox API key detected. Using <bold>anonymous open data access</bold> without authentication. "
                "For higher throughput and rate limits, sign up for a free account at https://console.tilebox.com."
                "</yellow>"
            )

        channel = open_channel(url, token)
        dataset_service_stub = with_pythonic_errors(DatasetServiceStub(channel))
        collection_service_stub = with_pythonic_errors(CollectionServiceStub(channel))
        data_access_service_stub = with_pythonic_errors(DataAccessServiceStub(channel))
        data_ingestion_service_stub = with_pythonic_errors(DataIngestionServiceStub(channel))
        service = TileboxDatasetService(
            dataset_service_stub, collection_service_stub, data_access_service_stub, data_ingestion_service_stub
        )
        self._client = BaseClient(service)

    def create_or_update_dataset(
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
            dataset = self.dataset(code_name)
        except NotFoundError:
            return self._client.create_dataset(kind, code_name, fields or [], name or code_name, DatasetClient).get()

        return self._client.update_dataset(
            kind,
            dataset._dataset.id,  # noqa: SLF001
            fields or [],
            name or dataset._dataset.name,  # noqa: SLF001
            DatasetClient,
        ).get()

    def datasets(self) -> Group:
        """Fetch all available datasets."""
        return self._client.datasets(DatasetClient).get()

    def dataset(self, slug: str) -> DatasetClient:
        """Get a dataset by its slug, e.g. `open_data.copernicus.sentinel1_sar`.

        Args:
            slug: The slug of the dataset.

        Returns:
            The dataset if it exists.
        """
        return self._client.dataset(slug, DatasetClient).get()

    def _dataset_by_id(self, dataset_id: str | UUID) -> DatasetClient:
        return self._client._dataset_by_id(dataset_id, DatasetClient).get()  # noqa: SLF001
