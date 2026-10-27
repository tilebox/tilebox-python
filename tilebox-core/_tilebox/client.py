"""Owned HTTP transports for native Connect clients."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Literal, Self, TypeAlias, TypeVar
from urllib.parse import urlsplit, urlunsplit

from connectrpc.client import ConnectClient, ConnectClientSync
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.interceptor import Interceptor, InterceptorSync
from connectrpc.request import RequestContext
from pyqwest import Client, HTTPTransport, HTTPVersion, SyncClient, SyncHTTPTransport

from _tilebox.client_metadata import client_metadata
from _tilebox.errors import translate_connect_error

Transport: TypeAlias = Literal["http2", "http1", "grpc"]

Sync = TypeVar("Sync", bound=ConnectClientSync)
Async = TypeVar("Async", bound=ConnectClient)
Req = TypeVar("Req")
Res = TypeVar("Res")


def _http_version(transport: Transport) -> HTTPVersion:
    match transport:
        case "http2":
            return HTTPVersion.HTTP2
        case "http1":
            return HTTPVersion.HTTP1
        case _:
            raise ValueError(f"Unsupported transport {transport!r}; use 'http2' or 'http1' (both use Connect)")


def _retry_delay(ctx: RequestContext, error: ConnectError, attempt: int) -> float | None:
    delay = min(0.02 * 3**attempt, 1.0)
    if (
        attempt >= 4
        or error.code not in {Code.UNAVAILABLE, Code.RESOURCE_EXHAUSTED}
        or ctx.timeout_ms is None
        or ctx.timeout_ms <= delay * 1000
    ):
        return None
    return delay


def connect_address(url: str, rpc_method_prefix: str | None = None) -> str:
    """Normalize endpoints, defaulting bare hosts to TLS and development ports to HTTP."""
    if url.startswith("unix:"):
        raise ValueError("Connect HTTP transport does not support unix socket URLs")
    if "://" not in url:
        parsed = urlsplit(f"//{url}")
        scheme = "http" if parsed.port not in (None, 443) else "https"
        url = f"{scheme}://{url}"
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in url)
    ):
        raise ValueError(f"Invalid URL: {url}")
    if parsed.scheme == "http" and parsed.port is None:
        raise ValueError("Explicit port required for insecure HTTP connection")
    if parsed.scheme == "https" and parsed.port == 443:
        url = urlunsplit((parsed.scheme, parsed.netloc.removesuffix(":443"), parsed.path, "", ""))
    prefix = (rpc_method_prefix or "").strip("/")
    return url.rstrip("/") + (f"/{prefix}" if prefix else "")


class _MetadataErrors:
    def __init__(self, token: str | None, address: str) -> None:
        self.headers = client_metadata()
        self.token = token
        self.prefix = urlsplit(address).path.rstrip("/")

    def _prepare(self, ctx: RequestContext) -> str:
        for name, value in self.headers.items():
            ctx.request_headers[name] = value
        if self.token is not None:
            ctx.request_headers["authorization"] = f"Bearer {self.token}"
        return f"{self.prefix}/{ctx.method.service_name}/{ctx.method.name}"

    def intercept_unary_sync(
        self,
        call_next: Callable[[Req, RequestContext], Res],
        request: Req,
        ctx: RequestContext,
    ) -> Res:
        method = self._prepare(ctx)
        attempt = 0
        while True:
            try:
                return call_next(request, ctx)
            except ConnectError as error:
                delay = _retry_delay(ctx, error, attempt)
                if delay is None:
                    raise translate_connect_error(error, method) from None
                time.sleep(delay)
                attempt += 1

    async def intercept_unary(
        self,
        call_next: Callable[[Req, RequestContext], Awaitable[Res]],
        request: Req,
        ctx: RequestContext,
    ) -> Res:
        method = self._prepare(ctx)
        attempt = 0
        while True:
            try:
                return await call_next(request, ctx)
            except ConnectError as error:
                delay = _retry_delay(ctx, error, attempt)
                if delay is None:
                    raise translate_connect_error(error, method) from None
                await asyncio.sleep(delay)
                attempt += 1


class Connection:
    """Share one explicitly owned HTTP transport across generated synchronous clients."""

    def __init__(
        self,
        url: str,
        token: str | None = None,
        rpc_method_prefix: str | None = None,
        *,
        transport: Transport = "http2",
        interceptors: Iterable[InterceptorSync] = (),
    ) -> None:
        self.address = connect_address(url, rpc_method_prefix)
        self.transport = "http2" if transport == "grpc" else transport
        self._transport = SyncHTTPTransport(http_version=_http_version(self.transport), tls_include_system_certs=True)
        self._http = SyncClient(self._transport)
        self._interceptors = (_MetadataErrors(token, self.address), *interceptors)
        self._closed = False

    def client(self, client_class: type[Sync]) -> Sync:
        """Construct a native generated client using this connection's HTTP client."""
        if self._closed:
            raise RuntimeError("Connection is closed")
        return client_class(
            self.address,
            http_client=self._http,
            interceptors=self._interceptors,
            read_max_bytes=512 * 1024 * 1024,
            timeout_ms=60_000,
        )

    def close(self) -> None:
        """Release this connection's transport; safe to call more than once."""
        if not self._closed:
            self._closed = True
            self._transport.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class AsyncConnection:
    """Share one explicitly owned HTTP transport across generated asynchronous clients."""

    def __init__(
        self,
        url: str,
        token: str | None = None,
        rpc_method_prefix: str | None = None,
        *,
        transport: Transport = "http2",
        interceptors: Iterable[Interceptor] = (),
    ) -> None:
        self.address = connect_address(url, rpc_method_prefix)
        self.transport = "http2" if transport == "grpc" else transport
        self._transport = HTTPTransport(http_version=_http_version(self.transport), tls_include_system_certs=True)
        self._http = Client(self._transport)
        self._interceptors = (_MetadataErrors(token, self.address), *interceptors)
        self._closed = False

    def client(self, client_class: type[Async]) -> Async:
        """Construct a native generated client without opening an event loop."""
        if self._closed:
            raise RuntimeError("Connection is closed")
        return client_class(
            self.address,
            http_client=self._http,
            interceptors=self._interceptors,
            read_max_bytes=512 * 1024 * 1024,
            timeout_ms=60_000,
        )

    async def close(self) -> None:
        """Release this connection's transport; safe to call more than once."""
        if not self._closed:
            self._closed = True
            await self._transport.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
