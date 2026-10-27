"""Exercise native generated clients against a real local HTTP endpoint and binary recordings."""

import base64
import gzip
import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import TypeAlias

import pytest
from connectrpc.client import ConnectClient, ConnectClientSync
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.method import IdempotencyLevel, MethodInfo
from connectrpc.request import RequestContext
from protobuf.wkt import Empty, Timestamp

from _tilebox.client import AsyncConnection, Connection, connect_address
from _tilebox.concurrency import concurrent_producer_consumer
from _tilebox.replay import Record, Replay
from tilebox.datasets import Client as DatasetsClient
from tilebox.datasets.aio import Client as AsyncDatasetsClient
from tilebox.datasets.v1.datasets_connect import DatasetServiceClient, DatasetServiceClientSync
from tilebox.datasets.v1.datasets_pb import ListDatasetsRequest, ListDatasetsResponse
from tilebox.errors import (
    AuthenticationError,
    NetworkError,
    RequestCanceledError,
    SubscriptionLimitExceededError,
    TileboxError,
    TooManyRequestsError,
)

Endpoint: TypeAlias = tuple[str, list[tuple[str, dict[str, str], bytes]]]


@pytest.fixture
def endpoint() -> Iterator[Endpoint]:
    """Serve minimal Connect unary responses and retain the received HTTP requests."""
    calls: list[tuple[str, dict[str, str], bytes]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            data = self.rfile.read(int(self.headers["Content-Length"]))
            if self.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            calls.append((self.path, dict(self.headers.items()), data))
            public = self.path.startswith("/public/")
            payload = (
                json.dumps({"code": "unimplemented", "message": "Not found"}).encode()
                if public
                else ListDatasetsResponse().to_binary()
            )
            self.send_response(501 if public else 200)
            self.send_header("Content-Type", "application/json" if public else "application/proto")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_http_metadata_record_and_replay(endpoint: Endpoint, tmp_path: Path) -> None:
    """Native clients send auth/metadata and binary requests; recorded calls replay without HTTP."""
    address, calls = endpoint
    recording = tmp_path / "calls.bin"
    request = ListDatasetsRequest()
    with Connection(address, "secret", transport="http1", interceptors=[Record(recording)]) as connection:
        first = connection.client(DatasetServiceClientSync)
        second = connection.client(DatasetServiceClientSync)
        assert first._http_client is second._http_client
        assert first._read_max_bytes == 512 * 1024 * 1024
        assert first.list_datasets(request) == ListDatasetsResponse()
    connection.close()
    with pytest.raises(RuntimeError, match="closed"):
        connection.client(DatasetServiceClientSync)

    path, headers, data = calls[0]
    assert path == "/datasets.v1.DatasetService/ListDatasets"
    headers = {name.lower(): value for name, value in headers.items()}
    assert headers["authorization"] == "Bearer secret"
    assert 'name="python"' in headers["tilebox-client"]
    assert "gzip" in headers["accept-encoding"]
    assert data == request.to_binary()
    assert recording.read_bytes().split(b"\n") == [
        path.encode(),
        base64.b64encode(request.to_binary()),
        b"0",
        b"",
        b"",
    ]
    with Connection("http://127.0.0.1:1", interceptors=[Replay(recording)]) as connection:
        assert connection.client(DatasetServiceClientSync).list_datasets(request) == ListDatasetsResponse()
    assert len(calls) == 1


def test_replay_compares_message_values_not_wire_field_order(tmp_path: Path) -> None:
    """Equivalent field orderings match, while a changed field still fails replay."""
    recording = tmp_path / "ordered.bin"
    recording.write_bytes(b"/test.Service/Call\n" + base64.b64encode(b"\x10\x1d\x08\x11") + b"\n0\n\n")
    method = MethodInfo(
        name="Call",
        service_name="test.Service",
        input=Timestamp,
        output=Empty,
        idempotency_level=IdempotencyLevel.UNKNOWN,
    )
    for seconds in (17, 18):
        with Connection("http://localhost:1", interceptors=[Replay(recording)]) as connection:
            client = connection.client(ConnectClientSync)
            request = Timestamp(seconds=seconds, nanos=29)
            if seconds == 17:
                assert client.execute_unary(request=request, method=method) == Empty()
            else:
                with pytest.raises(ValueError, match="differs"):
                    client.execute_unary(request=request, method=method)


@pytest.mark.asyncio
async def test_async_native_http_and_replay(endpoint: Endpoint, tmp_path: Path) -> None:
    """Async client construction is synchronous and async recording/replay uses native methods."""
    address, calls = endpoint
    recording = tmp_path / "async.bin"
    async with AsyncConnection(address, transport="http1", interceptors=[Record(recording)]) as connection:
        client = connection.client(DatasetServiceClient)
        assert await client.list_datasets(ListDatasetsRequest()) == ListDatasetsResponse()
    await connection.close()
    async with AsyncConnection(address, interceptors=[Replay(recording)]) as connection:
        assert (
            await connection.client(DatasetServiceClient).list_datasets(ListDatasetsRequest()) == ListDatasetsResponse()
        )
    assert len(calls) == 1


def test_public_route_errors_and_recorded_status(endpoint: Endpoint, tmp_path: Path) -> None:
    """Public missing routes explain authentication, and legacy numeric statuses remain readable."""
    address, calls = endpoint
    with (
        Connection(address, rpc_method_prefix="/public/", transport="http1") as connection,
        pytest.raises(AuthenticationError, match="ListDatasets is only available"),
    ):
        connection.client(DatasetServiceClientSync).list_datasets(ListDatasetsRequest())
    assert calls[0][0] == "/public/datasets.v1.DatasetService/ListDatasets"
    recording = tmp_path / "error.bin"
    # Record interceptors capture each attempt, including all five retryable failures.
    recording.write_bytes(b"/datasets.v1.DatasetService/ListDatasets\n\n14\nstatus: 429\n" * 5)
    with (
        Connection(address, rpc_method_prefix="public", interceptors=[Replay(recording)]) as connection,
        pytest.raises(TooManyRequestsError, match="create a free account"),
    ):
        connection.client(DatasetServiceClientSync).list_datasets(ListDatasetsRequest())


@pytest.mark.asyncio
async def test_public_clients_force_http1(endpoint: Endpoint) -> None:
    """The user-facing proxy fallback must reach the HTTP/1-only endpoint in both clients."""
    address, calls = endpoint
    with (
        DatasetsClient(url=f"{address}/public", transport="http1") as client,
        pytest.raises(AuthenticationError, match="ListDatasets is only available"),
    ):
        client.datasets()
    async with AsyncDatasetsClient(url=f"{address}/public", transport="http1") as async_client:
        with pytest.raises(AuthenticationError, match="ListDatasets is only available"):
            await async_client.datasets()
    assert len(calls) == 2


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("api.tilebox.com/", "https://api.tilebox.com/public"),
        ("localhost:8080", "http://localhost:8080/public"),
        ("https://api.tilebox.com:443", "https://api.tilebox.com/public"),
    ],
)
def test_connect_address(url: str, expected: str) -> None:
    """Bare hosts default to TLS while explicit development ports use HTTP."""
    assert connect_address(url, "/public/") == expected


def test_consumer_errors_propagate_without_deadlock() -> None:
    """Consumer failure unblocks a producer even when the bounded queue is full."""

    def fail(_: int) -> None:
        raise ValueError("consumer failed")

    with pytest.raises(ValueError, match="consumer failed"):
        concurrent_producer_consumer(iter(range(100)), fail, buffer_size=1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("idempotency", "code", "timeout_ms", "attempts", "expected_error"),
    [
        (IdempotencyLevel.UNKNOWN, Code.UNAVAILABLE, 60_000, 5, NetworkError),
        (IdempotencyLevel.UNKNOWN, Code.RESOURCE_EXHAUSTED, 60_000, 5, SubscriptionLimitExceededError),
        (IdempotencyLevel.UNKNOWN, Code.UNAUTHENTICATED, 60_000, 1, AuthenticationError),
        (IdempotencyLevel.UNKNOWN, Code.CANCELED, 60_000, 1, RequestCanceledError),
        (IdempotencyLevel.NO_SIDE_EFFECTS, Code.UNAVAILABLE, 60_000, 5, NetworkError),
        (IdempotencyLevel.IDEMPOTENT, Code.UNAVAILABLE, 1, 1, NetworkError),
    ],
)
async def test_retries_respect_error_code_attempt_limit_and_deadline(
    idempotency: IdempotencyLevel,
    code: Code,
    timeout_ms: int,
    attempts: int,
    expected_error: type[Exception],
) -> None:
    """Both invocation paths retry transient errors regardless of method idempotency."""
    assert issubclass(expected_error, TileboxError)

    class Failing:
        def __init__(self) -> None:
            self.calls = 0

        def intercept_unary_sync(self, call_next: object, request: Empty, ctx: RequestContext) -> Empty:
            _ = call_next, request, ctx
            self.calls += 1
            raise ConnectError(code, "request failed")

        async def intercept_unary(self, call_next: object, request: Empty, ctx: RequestContext) -> Empty:
            _ = call_next, request, ctx
            self.calls += 1
            raise ConnectError(code, "request failed")

    method = MethodInfo(
        name="Call", service_name="test.Service", input=Empty, output=Empty, idempotency_level=idempotency
    )
    failing = Failing()
    with (
        Connection("http://localhost:1", interceptors=[failing]) as connection,
        pytest.raises(expected_error),
    ):
        connection.client(ConnectClientSync).execute_unary(request=Empty(), method=method, timeout_ms=timeout_ms)
    assert failing.calls == attempts
    failing.calls = 0
    async with AsyncConnection("http://localhost:1", interceptors=[failing]) as connection:
        with pytest.raises(expected_error):
            await connection.client(ConnectClient).execute_unary(request=Empty(), method=method, timeout_ms=timeout_ms)
    assert failing.calls == attempts
