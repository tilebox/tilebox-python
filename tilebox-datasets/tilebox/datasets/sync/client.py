"""Synchronous datasets API backed by native Connect clients."""

from collections.abc import Sequence
from typing import Any, Self
from uuid import UUID

from _tilebox.client import Connection, Transport
from _tilebox.errors import NotFoundError
from tilebox.datasets.client import _construct_root_group, _log_server_message, connection_options
from tilebox.datasets.data.datasets import Dataset, DatasetKind, DatasetType, FieldDict, ListDatasetsResponse
from tilebox.datasets.group import Group
from tilebox.datasets.sync.dataset import DatasetClient
from tilebox.datasets.uuid import as_uuid, uuid_to_uuid_message
from tilebox.datasets.v1.datasets_connect import DatasetServiceClientSync
from tilebox.datasets.v1.datasets_pb import (
    CreateDatasetRequest,
    GetDatasetRequest,
    ListDatasetsRequest,
    UpdateDatasetRequest,
)


class Client:
    """Access datasets using blocking Connect RPCs."""

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
        self._connection = Connection(url, token, prefix, transport=transport, interceptors=interceptors)
        self._datasets = self._connection.client(DatasetServiceClientSync)

    def close(self) -> None:
        """Release the connection's HTTP resources."""
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def create_or_update_dataset(
        self, kind: DatasetKind, code_name: str, fields: list[FieldDict] | None = None, *, name: str | None = None
    ) -> DatasetClient:
        """Create a dataset, or update it if the slug already exists."""
        try:
            existing = Dataset.from_message(self._datasets.get_dataset(GetDatasetRequest(slug=code_name)))
        except NotFoundError:
            dataset = Dataset.from_message(
                self._datasets.create_dataset(
                    CreateDatasetRequest(
                        code_name=code_name,
                        name=name or code_name,
                        type=DatasetType.from_fields(kind, fields or []).to_message(),
                    )
                )
            )
        else:
            dataset = Dataset.from_message(
                self._datasets.update_dataset(
                    UpdateDatasetRequest(
                        id=uuid_to_uuid_message(existing.id),
                        name=name or existing.name,
                        type=DatasetType.from_fields(kind, fields or []).to_message(),
                    )
                )
            )
        return DatasetClient(self._connection, dataset)

    def datasets(self) -> Group:
        """Fetch the hierarchy of accessible datasets."""
        response = ListDatasetsResponse.from_message(self._datasets.list_datasets(ListDatasetsRequest()))
        _log_server_message(response)
        return _construct_root_group(
            [DatasetClient(self._connection, dataset) for dataset in response.datasets], response.groups
        )

    def dataset(self, slug: str) -> DatasetClient:
        """Fetch a dataset by slug."""
        return DatasetClient(
            self._connection, Dataset.from_message(self._datasets.get_dataset(GetDatasetRequest(slug=slug)))
        )

    def _dataset_by_id(self, dataset_id: str | UUID) -> DatasetClient:
        return DatasetClient(
            self._connection,
            Dataset.from_message(
                self._datasets.get_dataset(GetDatasetRequest(id=uuid_to_uuid_message(as_uuid(dataset_id))))
            ),
        )
