import os
from unittest.mock import MagicMock, patch

import pytest

from tilebox.datasets.aio import Client
from tilebox.datasets.client import _TILEBOX_API_URL, _TILEBOX_DEV_API_URL


@patch("tilebox.datasets.aio.client.AsyncConnection")
def test_tilebox_client_init_opens_channel(connection_mock: MagicMock) -> None:
    Client(url="some-url", token="some-token")  # noqa: S106
    connection_mock.assert_called_once_with("some-url", "some-token", None, transport="http2", interceptors=())


@pytest.mark.parametrize("url", [_TILEBOX_API_URL, _TILEBOX_DEV_API_URL, f"{_TILEBOX_API_URL}/"])
@patch.dict(os.environ, {}, clear=True)
@patch("tilebox.datasets.aio.client.AsyncConnection")
def test_tilebox_client_init_uses_public_rpc_prefix_for_tilebox_urls(connection_mock: MagicMock, url: str) -> None:
    Client(url=url, token=None)
    connection_mock.assert_called_once_with(url.removesuffix("/"), None, "/public", transport="http2", interceptors=())


@patch.dict(os.environ, {}, clear=True)
@patch("tilebox.datasets.aio.client.AsyncConnection")
def test_tilebox_client_init_skips_public_rpc_prefix_for_custom_urls(connection_mock: MagicMock) -> None:
    Client(url="some-url", token=None)
    connection_mock.assert_called_once_with("some-url", None, None, transport="http2", interceptors=())
