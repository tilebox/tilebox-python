import os
from uuid import UUID

from loguru import logger

from _tilebox.grpc.aio.syncify import Syncifiable
from _tilebox.grpc.channel import open_channel
from tilebox.datasets.group import TileboxDatasetGroup, construct_root_group
from tilebox.datasets.message_pool import register_once
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.timeseries import RemoteTimeseriesDataset


class Client(Syncifiable):
    def __init__(self, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        """
        A tilebox client that can be used to access the tilebox dataset API.

        Args:
            url: The URL of the tilebox server, defaults to https://api.tilebox.com
            token: The API key to use for authentication. If not provided, the TILEBOX_API_KEY environment variable
                will be used.
        """
        if token is None:  # if no token is provided, try to get it from the environment
            token = os.environ.get("TILEBOX_API_KEY", None)
        if url == "https://api.tilebox.com" and token is None:
            raise ValueError(
                "No API key provided and no TILEBOX_API_KEY environment variable set. Please specify an API key using "
                "the token argument. For example: `Client(token='YOUR_TILEBOX_API_KEY')`"
            )
        self._channel = open_channel(url, token)
        self._service = TileboxDatasetService(self._channel)

    async def datasets(self) -> TileboxDatasetGroup:
        response = await self._service.list_datasets()

        if response.server_message:
            logger.opt(colors=True).info(response.server_message + "\n")

        # we add the protobuf message types to the global message pool, so that we can deserialize datapoints
        for dataset in response.datasets:
            register_once(dataset.type)

        return self._finalize_datasets(construct_root_group(response.datasets, response.groups, self._service))

    async def dataset(self, dataset_id: str | UUID) -> RemoteTimeseriesDataset:
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
        return self._finalize_dataset(RemoteTimeseriesDataset(self._service, dataset))

    def _finalize_datasets(self, datasets: TileboxDatasetGroup) -> TileboxDatasetGroup:
        """Do some finalization on the datasets before returning them to the user."""
        # will be overwritten by _syncify() if this client is syncified to also return a syncified datasets object
        return datasets

    def _finalize_dataset(self, dataset: RemoteTimeseriesDataset) -> RemoteTimeseriesDataset:
        """Do some finalization on a dataset before returning it to the user."""
        # will be overwritten by _syncify() if this client is syncified to also return a syncified dataset object
        return dataset

    def _syncify(self) -> None:
        def _syncified_datasets(datasets: TileboxDatasetGroup) -> TileboxDatasetGroup:
            datasets._syncify()  # noqa: SLF001
            return datasets

        def _syncified_dataset(dataset: RemoteTimeseriesDataset) -> RemoteTimeseriesDataset:
            dataset._syncify()  # noqa: SLF001
            return dataset

        super()._syncify()
        self._finalize_datasets = _syncified_datasets
        self._finalize_dataset = _syncified_dataset
