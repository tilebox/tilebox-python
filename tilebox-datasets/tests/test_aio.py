from unittest.mock import MagicMock, patch

from tilebox.datasets.aio import Client


@patch("tilebox.datasets.aio.client.open_channel")
def test_tilebox_client_init_opens_channel(open_channel_mock: MagicMock) -> None:
    Client(url="some-url", token="some-token")  # noqa: S106
    open_channel_mock.assert_called_once_with("some-url", "some-token")
