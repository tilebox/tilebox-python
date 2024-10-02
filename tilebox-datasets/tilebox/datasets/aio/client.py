from uuid import UUID

from _tilebox.grpc.aio.channel import open_channel
from tilebox.datasets.aio.service import TileboxDatasetService
from tilebox.datasets.aio.timeseries import TimeseriesCollection, TimeseriesDataset
from tilebox.datasets.group import Group
from tilebox.datasets.message_pool import register_once
from tilebox.datasets.sync.client import _construct_root_group, _handle_list_datasets_response, _token_from_env


class Client:
    def __init__(self, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        """
        A async tilebox datasets client that can be used to interact with the tilebox dataset API.

        Args:
            url: The URL of the tilebox server, defaults to https://api.tilebox.com
            token: The API key to use for authentication. If not provided, the TILEBOX_API_KEY environment variable
                will be used.
        """
        self._channel = open_channel(url, _token_from_env(url, token))
        self._service = TileboxDatasetService(self._channel)

    async def datasets(self) -> Group:
        response = await self._service.list_datasets()
        _handle_list_datasets_response(response)
        return _construct_root_group(
            [TimeseriesDataset(self._service, dataset) for dataset in response.datasets], response.groups
        )

    async def dataset(self, dataset_id: str | UUID) -> TimeseriesDataset:
        """
        Get a dataset by its id.

        Args:
            dataset_id: The id of the dataset to get.

        Returns:
            The dataset if it exists.
        """
        if isinstance(dataset_id, str):
            dataset_id = UUID(dataset_id)
        dataset = await self._service.get_dataset(dataset_id)
        register_once(dataset.type)
        return TimeseriesDataset(self._service, dataset)


__all__ = ["Client", "TimeseriesDataset", "TimeseriesCollection"]
