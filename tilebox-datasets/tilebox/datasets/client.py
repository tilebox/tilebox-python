import os
import sys
from typing import Any, Protocol, TypeVar
from uuid import UUID

from loguru import logger
from promise import Promise

from _tilebox.grpc.channel import parse_channel_info
from tilebox.datasets.data.datasets import Dataset, DatasetGroup, ListDatasetsResponse
from tilebox.datasets.group import Group
from tilebox.datasets.message_pool import register_once
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.uuid import as_uuid


class TimeseriesDatasetLike(Protocol):
    def __init__(self, service: TileboxDatasetService, dataset: Dataset) -> None:
        pass


T = TypeVar("T", bound=TimeseriesDatasetLike)


class Client:
    def __init__(self, service: TileboxDatasetService) -> None:
        self._service = service

    def datasets(self, dataset_type: type[T]) -> Promise[Group]:
        """Fetch all available datasets."""
        return (
            self._service.list_datasets()
            .then(_log_server_message)
            .then(_ensure_all_registered)
            .then(
                lambda response: _construct_root_group(
                    [dataset_type(self._service, dataset) for dataset in response.datasets], response.groups
                )
            )
        )

    def dataset(self, slug: str, dataset_type: type[T]) -> Promise[T]:
        """
        Get a dataset by its slug, e.g. `open_data.copernicus.sentinel1_sar`.

        Args:
            slug: The slug of the dataset

        Returns:
            The dataset if it exists.
        """

        return (
            self._service.get_dataset_by_slug(slug)
            .then(_ensure_registered)
            .then(lambda dataset: dataset_type(self._service, dataset))
        )

    def _dataset_by_id(self, dataset_id: str | UUID, dataset_type: type[T]) -> Promise[T]:
        return (
            self._service.get_dataset_by_id(as_uuid(dataset_id))
            .then(_ensure_registered)
            .then(lambda dataset: dataset_type(self._service, dataset))
        )


def token_from_env(url: str, token: str | None) -> str | None:
    if token is None:  # if no token is provided, try to get it from the environment
        token = os.environ.get("TILEBOX_API_KEY", None)

    if token is None and parse_channel_info(url).address == "api.tilebox.com":
        raise ValueError(
            "No API key provided and no TILEBOX_API_KEY environment variable set. Please specify an API key using "
            "the token argument. For example: `Client(token='YOUR_TILEBOX_API_KEY')`"
        )

    return token


def _log_server_message(response: ListDatasetsResponse) -> ListDatasetsResponse:
    if response.server_message:
        logger.opt(colors=True).info(response.server_message + "\n")
    return response


def _ensure_registered(dataset: Dataset) -> Dataset:
    register_once(dataset.type)
    return dataset


def _ensure_all_registered(response: ListDatasetsResponse) -> ListDatasetsResponse:
    for dataset in response.datasets:
        register_once(dataset.type)
    return response


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
