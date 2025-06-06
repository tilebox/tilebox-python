from typing import TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from grpc import StatusCode
from grpc.aio import AioRpcError, ClientCallDetails
from grpc.aio._metadata import Metadata

from _tilebox.grpc.channel import (
    _CHANNEL_OPTIONS,
    _AuthMetadataInterceptor,
    _ErrorHandlerInterceptor,
    _parse_channel_info,
    open_channel,
)
from _tilebox.grpc.error import ArgumentError, AuthenticationError, InternalServerError, NotFoundError


@patch("_tilebox.grpc.channel.secure_channel")
def test_open_secure_channel(open_func: MagicMock) -> None:
    open_channel("api.adler-x.snamber.com")
    open_func.assert_called_once()
    assert open_func.call_args[0][0] == "api.adler-x.snamber.com:443"
    assert open_func.call_args[0][-1] == _CHANNEL_OPTIONS
    assert isinstance(open_func.call_args[1]["interceptors"][0], _ErrorHandlerInterceptor), "No error handler installed"


@patch("_tilebox.grpc.channel.insecure_channel")
def test_open_insecure_channel(open_func: MagicMock) -> None:
    open_channel("0.0.0.0:8083")
    open_func.assert_called_once()
    assert open_func.call_args[0][0] == "0.0.0.0:8083"
    assert open_func.call_args[0][-1] == _CHANNEL_OPTIONS
    assert isinstance(open_func.call_args[1]["interceptors"][0], _ErrorHandlerInterceptor), "No error handler installed"


@patch("_tilebox.grpc.channel.secure_channel")
def test_open_authenticated_channel(open_func: MagicMock) -> None:
    open_channel("api.adler-x.snamber.com", auth_token="very-secret")  # noqa: S106
    open_func.assert_called_once()

    assert open_func.call_args[1]["interceptors"][0]._auth == ("authorization", "Bearer very-secret")
    assert isinstance(open_func.call_args[1]["interceptors"][1], _ErrorHandlerInterceptor), "No error handler installed"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.adler-x.snamber.com",
        "api.adler-x.snamber.com",
        "https://api.adler-x.snamber.com:443",
        "api.adler-x.snamber.com:443",
        "https://api.adler-x.snamber.com/",
        "api.adler-x.snamber.com/",
        "https://api.adler-x.snamber.com:443/",
        "api.adler-x.snamber.com:443/",
    ],
)
def test_parse_channel_info_secure(url: str) -> None:
    channel_info = _parse_channel_info(url)
    assert channel_info.url_without_protocol == "api.adler-x.snamber.com:443"
    assert channel_info.use_ssl


@pytest.mark.parametrize(
    ("url", "expected_url_without_protocol"),
    [
        ("0.0.0.0:8083", "0.0.0.0:8083"),
        ("http://0.0.0.0:8083", "0.0.0.0:8083"),
        ("http://localhost:8083", "localhost:8083"),
        ("localhost:8083", "localhost:8083"),
        ("http://some.insecure.url:1234", "some.insecure.url:1234"),
    ],
)
def test_parse_channel_info_insecure(url: str, expected_url_without_protocol: str) -> None:
    channel_info = _parse_channel_info(url)
    assert channel_info.url_without_protocol == expected_url_without_protocol
    assert not channel_info.use_ssl


@pytest.mark.parametrize(
    "url",
    [
        "unix:path/to/s.sock",
        "unix:///path/to/s.sock",
    ],
)
def test_parse_channel_info_unix(url: str) -> None:
    channel_info = _parse_channel_info(url)
    assert channel_info.url_without_protocol == url
    assert not channel_info.use_ssl


def test_parse_channel_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid"):
        _parse_channel_info("i'm not a url")


def test_parse_channel_port_required_for_http() -> None:
    with pytest.raises(ValueError, match="Explicit port required"):
        _parse_channel_info("http://0.0.0.0")


@pytest.mark.asyncio()
@pytest.mark.parametrize("req_metadata", [None, [("some-other", "header")]])
async def test_auth_interceptor(req_metadata: None | list[tuple[str, str]]) -> None:
    """Test that the auth interceptor adds the auth token as metadata to every gRPC request"""
    interceptor = _AuthMetadataInterceptor("very-secret")

    mock_method = AsyncMock()

    await interceptor.intercept_unary_unary(
        mock_method, ClientCallDetails("/some-rpc-method", 10, req_metadata, None, True), AsyncMock()
    )

    mock_method.assert_called_once()
    updated_call_details = mock_method.call_args[0][0]
    assert ("authorization", "Bearer very-secret") in updated_call_details.metadata


E = TypeVar("E", bound=BaseException)


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("grpc_status", "exception_type"),
    [
        (StatusCode.UNAUTHENTICATED, AuthenticationError),
        (StatusCode.PERMISSION_DENIED, AuthenticationError),
        (StatusCode.NOT_FOUND, NotFoundError),
        (StatusCode.INVALID_ARGUMENT, ArgumentError),
        (StatusCode.INTERNAL, InternalServerError),
    ],
)
async def test_error_interceptor(grpc_status: StatusCode, exception_type: type[E]) -> None:
    """Test that the error handler interceptor successfully translates gRPC status codes to python exceptions"""
    interceptor = _ErrorHandlerInterceptor()

    grpc_error = AioRpcError(grpc_status, Metadata(), Metadata())

    with pytest.raises(exception_type, match=".*"):
        await interceptor.intercept_unary_unary(
            AsyncMock(side_effect=grpc_error),
            ClientCallDetails("/some-rpc-method", 10, None, None, True),
            AsyncMock(),
        )
