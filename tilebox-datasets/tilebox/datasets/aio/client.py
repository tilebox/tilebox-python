"""Asynchronous datasets API backed by native Connect clients."""

from collections.abc import Sequence
from typing import Any, Self
from uuid import UUID

from _tilebox.client import AsyncConnection, Transport
from _tilebox.errors import NotFoundError
from tilebox.datasets.aio.dataset import DatasetClient
from tilebox.datasets.client import _construct_root_group, _log_server_message, connection_options
from tilebox.datasets.data.datasets import Dataset, DatasetKind, DatasetType, FieldDict, ListDatasetsResponse
from tilebox.datasets.group import Group
from tilebox.datasets.uuid import as_uuid, uuid_to_uuid_message
from tilebox.datasets.v1.datasets_connect import DatasetServiceClient
from tilebox.datasets.v1.datasets_pb import (
    CreateDatasetRequest,
    GetDatasetRequest,
    ListDatasetsRequest,
    UpdateDatasetRequest,
)


class Client:
    """Access datasets using asynchronous Connect RPCs."""

    def __init__(
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        warn_if_unauthenticated: bool = True,
        transport: Transport = "http2",
        interceptors: Sequence[Any] = (),
    ) -> None:
        """Use Connect over HTTP/2 by default, or force HTTP/1 with transport="http1".

        The legacy transport="grpc" spelling is an alias for "http2".
        """
        url, token, prefix = connection_options(url, token, warn_if_unauthenticated)
        self._connection = AsyncConnection(url, token, prefix, transport=transport, interceptors=interceptors)
        self._datasets = self._connection.client(DatasetServiceClient)

    async def close(self) -> None:
        """Release the connection's HTTP resources."""
        await self._connection.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def create_or_update_dataset(
        self, kind: DatasetKind, code_name: str, fields: list[FieldDict] | None = None, *, name: str | None = None
    ) -> DatasetClient:
        """Create a dataset, or update it if the slug already exists."""
        try:
            existing = Dataset.from_message(await self._datasets.get_dataset(GetDatasetRequest(slug=code_name)))
        except NotFoundError:
            dataset = Dataset.from_message(
                await self._datasets.create_dataset(
                    CreateDatasetRequest(
                        code_name=code_name,
                        name=name or code_name,
                        type=DatasetType.from_fields(kind, fields or []).to_message(),
                    )
                )
            )
        else:
            dataset = Dataset.from_message(
                await self._datasets.update_dataset(
                    UpdateDatasetRequest(
                        id=uuid_to_uuid_message(existing.id),
                        name=name or existing.name,
                        type=DatasetType.from_fields(kind, fields or []).to_message(),
                    )
                )
            )
        return DatasetClient(self._connection, dataset)

    async def datasets(self) -> Group:
        """Fetch the hierarchy of accessible datasets."""
        response = ListDatasetsResponse.from_message(await self._datasets.list_datasets(ListDatasetsRequest()))
        _log_server_message(response)
        return _construct_root_group(
            [DatasetClient(self._connection, dataset) for dataset in response.datasets], response.groups
        )

    async def dataset(self, slug: str) -> DatasetClient:
        """Fetch a dataset by slug."""
        return DatasetClient(
            self._connection, Dataset.from_message(await self._datasets.get_dataset(GetDatasetRequest(slug=slug)))
        )

    async def _dataset_by_id(self, dataset_id: str | UUID) -> DatasetClient:
        return DatasetClient(
            self._connection,
            Dataset.from_message(
                await self._datasets.get_dataset(GetDatasetRequest(id=uuid_to_uuid_message(as_uuid(dataset_id))))
            ),
        )
