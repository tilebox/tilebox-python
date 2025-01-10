from _tilebox.grpc.channel import open_channel
from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.client import Client as BaseClient
from tilebox.datasets.client import token_from_env
from tilebox.datasets.datasetsv1.tilebox_pb2_grpc import TileboxServiceStub
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
        service = TileboxDatasetService(with_pythonic_errors(TileboxServiceStub(channel)))
        self._client = BaseClient(service)

    def datasets(self) -> Group:
        return self._client.datasets(TimeseriesDataset).get()

    def dataset(self, slug: str) -> TimeseriesDataset:
        return self._client.dataset(slug, TimeseriesDataset).get()

    def _dataset_by_id(self, dataset_id: str) -> TimeseriesDataset:
        return self._client._dataset_by_id(dataset_id, TimeseriesDataset).get()  # noqa: SLF001
