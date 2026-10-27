"""Configuration and result assembly shared by synchronous and asynchronous clients."""

import os
from typing import Any

from tilebox.datasets.data.datasets import DatasetGroup, ListDatasetsResponse
from tilebox.datasets.group import Group
from tilebox.datasets.notices import print_notice

_TILEBOX_API_URL = "https://api.tilebox.com"
_TILEBOX_DEV_API_URL = "https://api.tilebox.dev"
_TILEBOX_API_KEY_ENV_VAR = "TILEBOX_API_KEY"


def connection_options(
    url: str | None, token: str | None, warn_if_unauthenticated: bool
) -> tuple[str, str | None, str | None]:
    """Resolve credentials and anonymous public routing for Tilebox deployments."""
    url = (url or os.environ.get("TILEBOX_API_URL") or _TILEBOX_API_URL).rstrip("/")
    if token is None:
        token = os.environ.get(_TILEBOX_API_KEY_ENV_VAR)
    public = url in (_TILEBOX_API_URL, _TILEBOX_DEV_API_URL) and token is None
    if public and warn_if_unauthenticated:
        print_notice(
            "[yellow]No Tilebox API key detected. Using [bold]anonymous open data access[/bold] without authentication. "
            "For higher throughput and rate limits, sign up for a free account at https://console.tilebox.com.[/yellow]"
        )
    return url, token, "/public" if public else None


def _log_server_message(response: ListDatasetsResponse) -> None:
    if response.server_message:
        print_notice(response.server_message + "\n")


def _construct_root_group(datasets: list[Any], groups: list[DatasetGroup]) -> Group:
    root = Group()
    group_lookup = {g.id: Group() for g in groups}
    for group in groups:
        parent = group_lookup[group.parent_id] if group.parent_id is not None else root
        parent._add(group.code_name, group_lookup[group.id])  # noqa: SLF001
    for client in datasets:
        dataset = client._dataset  # noqa: SLF001
        group_lookup.get(dataset.group_id, root)._add(dataset.code_name, client)  # noqa: SLF001
    return root
