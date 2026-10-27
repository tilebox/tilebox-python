import asyncio
import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import niquests
import obstore
import pytest
from obstore.store import AzureStore, HTTPStore
from protobuf.wkt import Struct, Value

from tilebox.datasets.assets.assets import Asset, AssetLocation
from tilebox.datasets.stac.v1.authentication_pb import (
    AuthenticationFlow,
    AuthenticationParameter,
    AuthenticationScheme,
    KnownAuthenticationType,
    SignedURLFlow,
)
from tilebox.datasets.stac.v1.storage_pb import KnownStorageType, StorageScheme
from tilebox.storage.aio import Client


def _asset(container: str = "modis-061-cogs", path: str = "scene/red%20band.tif") -> Asset:
    return Asset(
        key="red",
        primary=AssetLocation(
            f"https://modiseuwest.blob.core.windows.net/{container}/{path}",
            storage_schemes={
                "arbitrary-storage-name": StorageScheme(
                    known_type=KnownStorageType.MICROSOFT_AZURE,
                    platform="https://{account}.blob.core.windows.net",
                    account="modiseuwest",
                    additional_properties={"container": Value.from_python(container)},
                )
            },
            authentication_schemes={
                "arbitrary-auth-name": AuthenticationScheme(
                    known_type=KnownAuthenticationType.SIGNED_URL,
                    flows=[
                        AuthenticationFlow(
                            key="authorizationCode",
                            signed_url=SignedURLFlow(
                                method="GET",
                                authorization_api="https://planetarycomputer.microsoft.com/api/sas/v1/sign",
                                parameters={
                                    "href": AuthenticationParameter(
                                        location="query", required=True, schema=Struct.from_python({"type": "string"})
                                    )
                                },
                                response_field="href",
                            ),
                        )
                    ],
                )
            },
        ),
    )


def test_resolution_is_offline_and_shares_stores_by_container() -> None:
    client = Client()
    asset = _asset()
    with patch.object(
        niquests.AsyncSession, "__init__", side_effect=AssertionError("resolution must not create a session")
    ):
        with ThreadPoolExecutor(max_workers=8) as executor:
            resolved = list(executor.map(client.resolve, [asset, _asset(path="scene/blue.tif")] * 8))
        assert len({id(item.store) for item in resolved}) == 1
        assert isinstance(resolved[0].store, AzureStore)
        assert resolved[0].href == asset.primary.href
        assert resolved[0].path == "scene/red band.tif"
        assert client.resolve(_asset(container="modis-061")).store is not resolved[0].store
        other_auth = _asset()
        other_auth.primary.authentication_schemes["arbitrary-auth-name"].description = "different configuration"
        assert client.resolve(other_auth).store is resolved[0].store
        public = Asset(key="preview", primary=AssetLocation(asset.primary.href))
        assert isinstance(client.resolve(public).store, HTTPStore)
        anonymous_azure = replace(asset, primary=replace(asset.primary, authentication_schemes={}))
        assert client.resolve(anonymous_azure).store is not resolved[0].store


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authorization_api", "https://evil.example/sign?sig=secret"),
        ("method", "POST"),
        ("response_field", "token"),
        ("parameters", {}),
    ],
)
def test_rejects_unsupported_signing_flows(field: str, value: Any) -> None:
    asset = _asset()
    flow = asset.primary.authentication_schemes["arbitrary-auth-name"].flows[0].signed_url
    assert flow is not None
    setattr(flow, field, value)
    with pytest.raises(ValueError, match="unsupported") as error:
        Client().resolve(asset)
    assert "secret" not in str(error.value)


def test_selects_registered_flow_without_requiring_annotation_details() -> None:
    asset = _asset()
    authentication = asset.primary.authentication_schemes["arbitrary-auth-name"]
    flow = authentication.flows[0]
    flow.key = "custom-flow-name"
    assert flow.signed_url is not None
    flow.signed_url.parameters = {
        "href": AuthenticationParameter(location="query"),
        "optional_hint": AuthenticationParameter(location="query", required=False),
    }
    authentication.flows.insert(
        0,
        AuthenticationFlow(key="other-service", signed_url=SignedURLFlow(authorization_api="https://example.com/sign")),
    )
    incompatible = AuthenticationFlow.from_binary(flow.to_binary())
    assert incompatible.signed_url is not None
    incompatible.signed_url.method = "POST"
    authentication.flows.insert(0, incompatible)
    resolved = Client().resolve(asset)
    assert isinstance(resolved.store, AzureStore)
    assert resolved.path == "scene/red band.tif"

    authentication.flows.append(flow)
    with pytest.raises(ValueError, match="multiple supported signed URL flows"):
        Client().resolve(asset)


@pytest.mark.parametrize(
    "href",
    [
        "https://otheraccount.blob.core.windows.net/modis-061-cogs/data.tif",
        "https://modiseuwest.blob.core.windows.net/modis-061/data.tif",
        "https://modiseuwest.blob.core.windows.net.evil.example/modis-061-cogs/data.tif",
        "http://modiseuwest.blob.core.windows.net/modis-061-cogs/data.tif",
        "https://modiseuwest.blob.core.windows.net/modis-061-cogs/data.tif?sig=secret",
    ],
)
def test_rejects_href_mismatches_without_leaking_queries(href: str) -> None:
    original = _asset().primary
    asset = Asset(
        key="red",
        primary=AssetLocation(href, original.storage_schemes, original.authentication_schemes),
    )
    with pytest.raises(ValueError, match="unable to resolve") as error:
        Client().resolve(asset)
    assert "secret" not in str(error.value)


@pytest.fixture
def pc_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Exercise real niquests and obstore against a local token and blob service."""
    state: dict[str, Any] = {"tokens": 0, "responses": [], "ttl": 3600, "blob_queries": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path.startswith("/api/sas/v1/token/"):
                state["tokens"] += 1
                expiry = (datetime.now(UTC) + timedelta(seconds=state["ttl"])).isoformat()
                status, payload = (
                    state["responses"].pop(0)
                    if state["responses"]
                    else (200, {"token": f"sig=token{state['tokens']}&se={expiry}", "msft:expiry": expiry})
                )
                data = json.dumps(payload).encode()
            else:
                query = parse_qs(parsed.query)
                state["blob_queries"].append(query)
                status = 200 if query.get("sig") else 403
                data = parsed.path.encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("ETag", '"test-etag"')
            self.send_header("Last-Modified", "Mon, 12 Oct 2026 12:00:00 GMT")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    original_get = niquests.AsyncSession.get

    async def local_token_get(session: niquests.AsyncSession, url: str, **kwargs: Any) -> Any:
        assert url.startswith("https://planetarycomputer.microsoft.com/api/sas/v1/token/modiseuwest/")
        return await original_get(session, origin + urlsplit(url).path, **kwargs)

    def local_store(container: str, **kwargs: Any) -> AzureStore:
        kwargs["endpoint"] = origin
        return AzureStore(container, client_options={"allow_http": True}, **kwargs)

    monkeypatch.setattr(niquests.AsyncSession, "get", local_token_get)
    monkeypatch.setattr(obstore.store, "AzureStore", local_store)
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.asyncio
async def test_reads_share_credentials_and_refresh_on_demand(pc_server: dict[str, Any], tmp_path: Path) -> None:
    client = Client()
    asset = _asset(path="scene/red.tif")
    pc_server["ttl"] = 60  # Inside obstore's five-minute refresh window.
    assert await client.read_bytes(asset) == b"/modis-061-cogs/scene/red.tif"
    assert pc_server["tokens"] == 1
    await asyncio.sleep(0.15)  # Beyond obstore's 100 ms minimum token reuse interval.
    pc_server["ttl"] = 3600
    reads = await asyncio.gather(*(client.read_bytes(_asset(path=f"scene/band{i}.tif")) for i in range(8)))
    assert reads == [f"/modis-061-cogs/scene/band{i}.tif".encode() for i in range(8)]
    assert pc_server["tokens"] == 2
    assert all(query["sig"] == ["token2"] for query in pc_server["blob_queries"][1:])
    await asyncio.sleep(0.15)
    destination = await client.download(asset, tmp_path / "red.tif")
    assert destination.read_bytes() == b"/modis-061-cogs/scene/red.tif"
    assert pc_server["tokens"] == 2
    assert await client.read_bytes(_asset(container="modis-061", path="original.hdf")) == b"/modis-061/original.hdf"
    assert pc_server["tokens"] == 3


@pytest.mark.asyncio
async def test_azure_uri_aliases_share_signing_for_objects_and_prefixes(pc_server: dict[str, Any]) -> None:
    client = Client()
    asset = _asset(path="scene/data.zarr")
    original = client.resolve(asset)
    for href in (
        "az://modiseuwest/modis-061-cogs/scene/data.zarr",
        "azure://modiseuwest/modis-061-cogs/scene/data.zarr",
        "abfs://modis-061-cogs@modiseuwest.dfs.core.windows.net/scene/data.zarr",
        "abfss://modis-061-cogs@modiseuwest.dfs.core.windows.net/scene/data.zarr",
        "abfs://modis-061-cogs/scene/data.zarr",
        "abfss://modis-061-cogs/scene/data.zarr",
    ):
        resolved = client.resolve(replace(asset, primary=replace(asset.primary, href=href)))
        assert resolved.store is original.store
        assert resolved.path == "scene/data.zarr"
        assert resolved.href == href
    # A future Zarr reader can use this prefix with the same store for every key.
    for key in ("zarr.json", "temperature/c/0/1"):
        result = await obstore.get_async(original.store, f"{original.path}/{key}")
        assert bytes(await result.bytes_async()) == f"/modis-061-cogs/scene/data.zarr/{key}".encode()
    assert pc_server["tokens"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_retries_transient_token_failures(pc_server: dict[str, Any], status: int) -> None:
    pc_server["responses"] = [(status, {"error": "secret"})] * 2
    assert await Client().read_bytes(_asset(path="data.json")) == b"/modis-061-cogs/data.json"
    assert pc_server["tokens"] == 3


@pytest.mark.asyncio
async def test_token_retries_are_bounded(pc_server: dict[str, Any]) -> None:
    pc_server["responses"] = [(503, {"error": "secret"})] * 3
    with pytest.raises(obstore.exceptions.UnauthenticatedError, match="token request failed") as error:
        await Client().read_bytes(_asset())
    assert "secret" not in str(error.value)
    assert pc_server["tokens"] == 3
    assert pc_server["blob_queries"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "payload"),
    [
        (403, {"error": "secret"}),
        (302, {"href": "https://evil.example/?sig=secret"}),
        (200, {"token": "secret", "msft:expiry": "2099-01-01T00:00:00Z"}),
        (200, {"token": "sig=secret&se=2099-01-01", "msft:expiry": "2099-01-01T00:00:00"}),
        (200, {"token": "sig=secret&se=2000-01-01", "msft:expiry": "2000-01-01T00:00:00Z"}),
        (200, {"token": "sig=secret&se=2099-01-01", "msft:expiry": "secret"}),
        (200, None),
    ],
)
async def test_invalid_credentials_fail_safely_and_are_not_cached(
    pc_server: dict[str, Any], status: int, payload: Any
) -> None:
    pc_server["responses"] = [(status, payload)]
    client = Client()
    with pytest.raises(obstore.exceptions.UnauthenticatedError, match="Planetary Computer") as error:
        await client.read_bytes(_asset(path="data.json"))
    assert "secret" not in str(error.value)
    assert pc_server["tokens"] == 1
    assert pc_server["blob_queries"] == []
    assert await client.read_bytes(_asset(path="data.json")) == b"/modis-061-cogs/data.json"
    assert pc_server["tokens"] == 2
