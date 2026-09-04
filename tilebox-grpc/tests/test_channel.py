from unittest.mock import MagicMock, patch

import pytest

from _tilebox.grpc.channel import (
    CHANNEL_OPTIONS,
    AsyncConnectStubAdapter,
    ChannelProtocol,
    ClientCallDetails,
    ConnectStubAdapter,
    _ClientMetadataInterceptor,
    _RpcMethodPrefixInterceptor,
    connect_address,
    open_channel,
    parse_channel_info,
)
from _tilebox.grpc.client_metadata import CLIENT_HEADER


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


@patch("_tilebox.grpc.channel.client_metadata", return_value={CLIENT_HEADER: 'name="python"'})
def test_client_metadata_interceptor(client_metadata: MagicMock) -> None:
    interceptor = _ClientMetadataInterceptor()
    continuation = MagicMock()

    interceptor.intercept_unary_unary(
        continuation,
        ClientCallDetails("/some-rpc-method", 10, [("authorization", "Bearer token")], None, True),
        MagicMock(),
    )

    client_metadata.assert_called_once_with()
    metadata = continuation.call_args[0][0].metadata
    assert ("authorization", "Bearer token") in metadata
    assert (CLIENT_HEADER.lower(), 'name="python"') in metadata


class _ConnectClient:
    def get_value(self, request: str, *, headers: dict[str, str]) -> tuple[str, dict[str, str]]:
        return request, headers


class _AsyncConnectClient:
    async def get_value(self, request: str, *, headers: dict[str, str]) -> tuple[str, dict[str, str]]:
        return request, headers


@patch("_tilebox.grpc.channel.client_metadata", return_value={CLIENT_HEADER: 'name="python"'})
def test_connect_stub_adapter_adds_client_metadata(client_metadata: MagicMock) -> None:
    adapter = ConnectStubAdapter(_ConnectClient(), {"authorization": "Bearer token"})

    request, headers = adapter.GetValue("request")  # ty: ignore[unresolved-attribute]  # added dynamically

    assert request == "request"
    assert headers == {
        "authorization": "Bearer token",
        CLIENT_HEADER: 'name="python"',
    }
    client_metadata.assert_called_once_with()


@pytest.mark.asyncio
@patch("_tilebox.grpc.channel.client_metadata", return_value={CLIENT_HEADER: 'name="python"'})
async def test_async_connect_stub_adapter_adds_client_metadata(client_metadata: MagicMock) -> None:
    adapter = AsyncConnectStubAdapter(_AsyncConnectClient(), {"authorization": "Bearer token"})

    request, headers = await adapter.GetValue("request")  # ty: ignore[unresolved-attribute]  # added dynamically

    assert request == "request"
    assert headers == {
        "authorization": "Bearer token",
        CLIENT_HEADER: 'name="python"',
    }
    client_metadata.assert_called_once_with()


@patch("_tilebox.grpc.channel.intercept_channel")
@patch("_tilebox.grpc.channel.secure_channel")
def test_open_channel_with_rpc_method_prefix(open_func: MagicMock, intercept_func: MagicMock) -> None:
    open_channel("api.tilebox.com", rpc_method_prefix="/public")
    open_func.assert_called_once()
    intercept_func.assert_called_once()

    assert intercept_func.call_args[0][2]._prefix == "/public"


def test_rpc_method_prefix_interceptor() -> None:
    interceptor = _RpcMethodPrefixInterceptor("/public")
    continuation = MagicMock()

    interceptor.intercept_unary_unary(
        continuation,
        ClientCallDetails("/datasets.v1.DatasetService/ListDatasets", 10, None, None, True),
        MagicMock(),
    )

    continuation.assert_called_once()
    updated_call_details = continuation.call_args[0][0]
    assert updated_call_details.method == "/public/datasets.v1.DatasetService/ListDatasets"


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


@pytest.mark.parametrize(
    ("url", "expected_address"),
    [
        ("https://api.tilebox.com", "https://api.tilebox.com"),
        ("api.tilebox.com", "https://api.tilebox.com"),
        ("https://api.tilebox.com:443", "https://api.tilebox.com"),
        ("https://api.tilebox.com/", "https://api.tilebox.com"),
        ("https://api.tilebox.com:8443", "https://api.tilebox.com:8443"),
        ("localhost:8083", "http://localhost:8083"),
        ("http://localhost:8083/", "http://localhost:8083"),
    ],
)
def test_connect_address(url: str, expected_address: str) -> None:
    assert connect_address(url) == expected_address


def test_connect_address_with_rpc_method_prefix() -> None:
    assert connect_address("api.tilebox.com/", "/public/") == "https://api.tilebox.com/public"


def test_connect_address_unix_unsupported() -> None:
    with pytest.raises(ValueError, match=r"does not support unix socket"):
        connect_address("unix:path/to/s.sock")
