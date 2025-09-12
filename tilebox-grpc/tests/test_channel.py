from unittest.mock import MagicMock, patch

import pytest

from _tilebox.grpc.channel import (
    CHANNEL_OPTIONS,
    ChannelProtocol,
    open_channel,
    parse_channel_info,
)


@patch("_tilebox.grpc.channel.secure_channel")
def test_open_secure_channel(open_func: MagicMock) -> None:
    open_channel("api.tilebox.com")
    open_func.assert_called_once()
    assert open_func.call_args[0][0] == "api.tilebox.com:443"
    assert open_func.call_args[0][-1] == CHANNEL_OPTIONS


@patch("_tilebox.grpc.channel.insecure_channel")
def test_open_insecure_channel(open_func: MagicMock) -> None:
    open_channel("0.0.0.0:8083")
    open_func.assert_called_once()
    assert open_func.call_args[0][0] == "0.0.0.0:8083"
    assert open_func.call_args[0][-1] == CHANNEL_OPTIONS


@patch("_tilebox.grpc.channel.intercept_channel")
@patch("_tilebox.grpc.channel.secure_channel")
def test_open_authenticated_channel(open_func: MagicMock, intercept_func: MagicMock) -> None:
    open_channel("api.tilebox.com", auth_token="very-secret")  # noqa: S106
    open_func.assert_called_once()
    intercept_func.assert_called_once()

    assert intercept_func.call_args[0][1]._auth == ("authorization", "Bearer very-secret")


@pytest.mark.parametrize(
    "url",
    [
        "https://api.tilebox.com",
        "api.tilebox.com",
        "https://api.tilebox.com:443",
        "api.tilebox.com:443",
        "https://api.tilebox.com/",
        "api.tilebox.com/",
        "https://api.tilebox.com:443/",
        "api.tilebox.com:443/",
    ],
)
def test_parse_channel_info_secure(url: str) -> None:
    channel_info = parse_channel_info(url)
    assert channel_info.address == "api.tilebox.com"
    assert channel_info.port == 443
    assert channel_info.protocol == ChannelProtocol.HTTPS


@pytest.mark.parametrize(
    ("url", "expected_url_without_protocol"),
    [
        ("0.0.0.0:8083", "0.0.0.0"),  # noqa: S104
        ("http://0.0.0.0:8083", "0.0.0.0"),  # noqa: S104
        ("http://localhost:8083", "localhost"),
        ("localhost:8083", "localhost"),
        ("http://some.insecure.url:8083", "some.insecure.url"),
    ],
)
def test_parse_channel_info_insecure(url: str, expected_url_without_protocol: str) -> None:
    channel_info = parse_channel_info(url)
    assert channel_info.address == expected_url_without_protocol
    assert channel_info.port == 8083
    assert channel_info.protocol == ChannelProtocol.HTTP


@pytest.mark.parametrize(
    "url",
    [
        "unix:path/to/s.sock",
        "unix:///path/to/s.sock",
    ],
)
def test_parse_channel_info_unix(url: str) -> None:
    channel_info = parse_channel_info(url)
    assert channel_info.address == url
    assert channel_info.port == 0
    assert channel_info.protocol == ChannelProtocol.UNIX


def test_parse_channel_invalid() -> None:
    with pytest.raises(ValueError, match=r"Invalid"):
        parse_channel_info("i'm not a url")


def test_parse_channel_port_required_for_http() -> None:
    with pytest.raises(ValueError, match=r"Explicit port required"):
        parse_channel_info("http://0.0.0.0")
