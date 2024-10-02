import os
import sys
from typing import Any
from uuid import UUID

from loguru import logger

from _tilebox.grpc.channel import open_channel
from tilebox.datasets.data.datasets import DatasetGroup, ListDatasetsResponse
from tilebox.datasets.group import Group
from tilebox.datasets.message_pool import register_once
from tilebox.datasets.sync.service import TileboxDatasetService
from tilebox.datasets.sync.timeseries import TimeseriesDataset


class Client:
    def __init__(self, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        self._channel = open_channel(url, _token_from_env(url, token))
        self._service = TileboxDatasetService(self._channel)

    def datasets(self) -> Group:
        response = self._service.list_datasets()

        _handle_list_datasets_response(response)
        return _construct_root_group(
            [TimeseriesDataset(self._service, dataset) for dataset in response.datasets], response.groups
        )

    def dataset(self, dataset_id: str | UUID) -> TimeseriesDataset:
        """
        Get a dataset by its id.

        Args:
            dataset_id: The id of the dataset to get.

        Returns:
            The dataset if it exists.
        """
        if isinstance(dataset_id, str):
            dataset_id = UUID(dataset_id)
        dataset = self._service.get_dataset(dataset_id)
        register_once(dataset.type)
        return TimeseriesDataset(self._service, dataset)


def _token_from_env(url: str, token: str | None) -> str | None:
    if token is None:  # if no token is provided, try to get it from the environment
        token = os.environ.get("TILEBOX_API_KEY", None)
    if "api.tilebox.com" in url and token is None:
        raise ValueError(
            "No API key provided and no TILEBOX_API_KEY environment variable set. Please specify an API key using "
            "the token argument. For example: `Client(token='YOUR_TILEBOX_API_KEY')`"
        )
    return token


def _handle_list_datasets_response(response: ListDatasetsResponse) -> None:
    if response.server_message:
        logger.opt(colors=True).info(response.server_message + "\n")

    # we add the protobuf message types to the global message pool, so that we can deserialize datapoints
    for dataset in response.datasets:
        register_once(dataset.type)


def _construct_root_group(
    datasets: list[Any],
    groups: list[DatasetGroup],
) -> Group:
    root = Group()
    group_lookup = {g.id: Group() for g in groups}

    # recursively nest groups based on their parent_id
    for g in groups:
        parent = group_lookup[g.parent_id] if g.parent_id is not None else root
        parent._add(g.code_name, group_lookup[g.id])  # noqa: SLF001

    # add datasets to their respective groups
    for d in datasets:
        dataset = d._dataset  # noqa: SLF001
        group = group_lookup[dataset.group_id]
        group._add(dataset.code_name, d)  # noqa: SLF001

    return root


__all__ = ["Client"]


def _init_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stdout, level=level, format="{message}", catch=True)


def _is_debug() -> bool:
    try:
        return bool(int(os.environ.get("TILEBOX_DEBUG") or 0))
    except (TypeError, ValueError):
        return False


if _is_debug():
    _init_logging("DEBUG")
else:
    _init_logging()
