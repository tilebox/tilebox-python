import os
from unittest.mock import MagicMock, patch

import pytest

from tilebox.datasets.aio import Client
from tilebox.datasets.client import _TILEBOX_API_URL, _TILEBOX_DEV_API_URL


@patch("tilebox.datasets.aio.client.open_channel")
def test_tilebox_client_init_opens_channel(open_channel_mock: MagicMock) -> None:
    Client(url="some-url", token="some-token")  # noqa: S106
    open_channel_mock.assert_called_once_with("some-url", "some-token", rpc_method_prefix=None)


@pytest.mark.parametrize("url", [_TILEBOX_API_URL, _TILEBOX_DEV_API_URL, f"{_TILEBOX_API_URL}/"])
@patch.dict(os.environ, {}, clear=True)
@patch("tilebox.datasets.aio.client.open_channel")
def test_tilebox_client_init_uses_public_rpc_prefix_for_tilebox_urls(open_channel_mock: MagicMock, url: str) -> None:
    Client(url=url, token=None)
    open_channel_mock.assert_called_once_with(url.removesuffix("/"), None, rpc_method_prefix="/public")


@patch.dict(os.environ, {}, clear=True)
@patch("tilebox.datasets.aio.client.open_channel")
def test_tilebox_client_init_skips_public_rpc_prefix_for_custom_urls(open_channel_mock: MagicMock) -> None:
    Client(url="some-url", token=None)
    open_channel_mock.assert_called_once_with("some-url", None, rpc_method_prefix=None)
