from uuid import UUID

from _tilebox.grpc.channel import open_channel
from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.client import Client as BaseClient
from tilebox.datasets.client import token_from_env
from tilebox.datasets.datasetsv1.tilebox_pb2_grpc import TileboxServiceStub
from tilebox.datasets.group import Group
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.sync.timeseries import TimeseriesDataset


class Client:
    def __init__(self, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        channel = open_channel(url, token_from_env(url, token))
        service = TileboxDatasetService(with_pythonic_errors(TileboxServiceStub(channel)))
        self._client = BaseClient(service)

    def datasets(self) -> Group:
        return self._client.datasets(TimeseriesDataset).get()

    def dataset(self, dataset_id: str | UUID) -> TimeseriesDataset:
        return self._client.dataset(dataset_id, TimeseriesDataset).get()
