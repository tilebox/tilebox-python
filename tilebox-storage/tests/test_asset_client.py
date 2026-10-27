import json
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

import numpy as np
import obstore
import pytest
import xarray as xr
from obstore.store import AzureStore, GCSStore, HTTPStore, LocalStore, S3Store

from tilebox.datasets.assets import AssetCollection
from tilebox.datasets.assets.assets import Asset, AssetLocation
from tilebox.datasets.stac.v1.asset_pb import Assets
from tilebox.datasets.stac.v1.authentication_pb import (
    Authentication,
    AuthenticationScheme,
    KnownAuthenticationType,
)
from tilebox.datasets.stac.v1.storage_pb import KnownStorageType, Storage, StorageScheme
from tilebox.storage.aio import AssetAccessPolicy, Client

if TYPE_CHECKING:
    from obstore.store import S3Credential


def _asset(location: AssetLocation, **kwargs: Any) -> Asset:
    return Asset(key="data", primary=location, **kwargs)


@pytest.mark.parametrize(
    ("sample", "store_type", "href", "options"),
    [
        pytest.param(
            "sentinel1",
            S3Store,
            "s3://sentinel-s1-l1c/GRD/2020/1/1/IW/DV/"
            "S1B_IW_GRDH_1SDV_20200101T000510_20200101T000539_019616_02512B_B140/measurement/iw-vv.tiff",
            {"region": "eu-central-1", "request_payer": "false"},
            id="aws-earth-sentinel1",
        ),
        pytest.param(
            "sentinel2",
            S3Store,
            "s3://e84-earth-search-sentinel-data/sentinel-2-c1-l2a/11/X/NM/2026/7/"
            "S2B_T11XNM_20260701T000137_L2A/B04.tif",
            {"region": "us-west-2", "request_payer": "false"},
            id="aws-earth-sentinel2",
        ),
        pytest.param(
            "wyvern",
            HTTPStore,
            "https://wyvern-data.com/wyvern_dragonette-001_20240506T061223_fb944bb4_l2a/"
            "wyvern_dragonette-001_20240506T061223_fb944bb4_l2a.tiff",
            {},
            id="wyvern-dragonette",
        ),
        pytest.param(
            "planet",
            GCSStore,
            "gs://open-cogs/planet-stac/tanager1-release2-core-imagery/"
            "ortho_visual/20240925_185504_87_4001_ortho_visual.tif",
            {},
            id="planet-tanager",
        ),
        pytest.param(
            "satellogic",
            S3Store,
            "s3://satellogic-earthview/data/tif/zone=36N/region=362863_5817776/date=2022-07-01/"
            "20220701_085711_SN18_36N_362863_5817776_TOA.tif",
            {},
            id="satellogic-earth-view",
        ),
        pytest.param(
            "planetary_computer",
            AzureStore,
            "https://modiseuwest.blob.core.windows.net/modis-061-cogs/MOD13Q1/35/10/2026193/"
            "MOD13Q1.A2026193.h35v10.061.2026210034525_250m_16_days_NDVI.tif",
            {"account_name": "modiseuwest", "container_name": "modis-061-cogs", "skip_signature": "false"},
            id="planetary-computer-modis",
        ),
    ],
)
def test_resolve_real_catalog_assets(
    sample: str, store_type: type[S3Store | GCSStore | HTTPStore | AzureStore], href: str, options: dict[str, str]
) -> None:
    """Resolve captured metadata through public APIs without reading source bytes.

    Captured on 2026-10-14 with ``tilebox dataset query <dataset>`.
    """
    fixture = json.loads((Path(__file__).parent / "testdata" / "asset_access.json").read_text())[sample]
    messages = {"assets": Assets, "storage": Storage, "authentication": Authentication}
    datapoint = xr.Dataset(
        {
            name: xr.DataArray(np.array(message.from_json(json.dumps(fixture[name])), dtype=object))
            for name, message in messages.items()
            if name in fixture
        }
    )
    asset = next(iter(AssetCollection.from_datapoint(datapoint).values()))
    resolved = Client().resolve(asset)

    assert isinstance(resolved.store, store_type)
    assert resolved.href == href
    expected = urlsplit(href)
    expected_path = expected.path.lstrip("/")
    if isinstance(resolved.store, AzureStore):
        assert resolved.authentication_scheme is not None
        assert resolved.authentication_scheme.known_type == KnownAuthenticationType.SIGNED_URL
        assert callable(resolved.store.credential_provider)
        expected_path = expected_path.removeprefix(f"{options['container_name']}/")
    else:
        assert resolved.authentication_scheme is None
    assert resolved.path == expected_path
    if isinstance(resolved.store, HTTPStore):
        assert resolved.store.url == f"{expected.scheme}://{expected.netloc}/"
    else:
        if not isinstance(resolved.store, AzureStore):
            assert resolved.store.config["bucket"] == expected.netloc
            assert resolved.store.config["skip_signature"] == "true"
            assert resolved.store.credential_provider is None
        for key, value in options.items():
            assert resolved.store.config[key] == value


def test_new_aio_api_does_not_introduce_root_client_or_eager_geotiff_import() -> None:
    code = (
        "import sys\n"
        "import tilebox.storage as storage\n"
        "assert not hasattr(storage, 'Client')\n"
        "from tilebox.storage.aio import Client, download, iter_bytes, open_geotiff, read_bytes\n"
        "assert Client and download and iter_bytes and open_geotiff and read_bytes\n"
        "assert 'async_geotiff' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603


def test_resolve_prefers_s3_and_reuses_store() -> None:
    scheme = StorageScheme(known_type=KnownStorageType.AWS_S3, region="us-west-2", requester_pays=False)
    schemes = MappingProxyType({"earth-search": scheme})
    primary = AssetLocation("https://example.com/data.tif", schemes)
    alternate = AssetLocation("s3://bucket/path/data.tif", schemes)
    asset = _asset(primary, alternates=MappingProxyType({"s3": alternate}))
    client = Client()

    with patch("obstore.store.S3Store") as store_class:
        store = object()
        store_class.return_value = store
        first = client.resolve(asset)
        second = client.resolve(asset)

    assert first.location is alternate
    assert first.store is second.store is store
    assert first.path == "path/data.tif"
    store_class.assert_called_once_with(
        "bucket",
        region="us-west-2",
        request_payer=False,
        skip_signature=True,
    )


def test_concurrent_resolution_constructs_one_store() -> None:
    asset = _asset(AssetLocation("s3://bucket/data.tif"))
    client = Client()
    with patch("obstore.store.S3Store") as store_class:
        store_class.return_value = object()
        with ThreadPoolExecutor(max_workers=8) as executor:
            stores = list(executor.map(lambda _: client.resolve(asset).store, range(32)))
    assert len({id(store) for store in stores}) == 1
    store_class.assert_called_once()


def test_resolution_rejection_details_and_client_policy() -> None:
    auth = AuthenticationScheme(known_type=KnownAuthenticationType.OAUTH2)
    first = StorageScheme(known_type=KnownStorageType.AWS_S3)
    second = StorageScheme(known_type=KnownStorageType.AWS_S3)
    asset = _asset(
        AssetLocation(
            "s3://bucket/data.tif",
            MappingProxyType({"first": first, "second": second}),
        )
    )
    client = Client()

    with pytest.raises(ValueError, match=r"primary.*multiple supported storage/authentication"):
        client.resolve(asset)
    authenticated = _asset(
        AssetLocation("s3://bucket/data.tif", authentication_schemes=MappingProxyType({"oauth": auth}))
    )
    with pytest.raises(ValueError, match=r"authentication type 'oauth2'.*unsupported"):
        client.resolve(authenticated)

    primary = AssetLocation("https://example.com/data.tif")
    alternate = AssetLocation("s3://bucket/data.tif")
    location = (
        Client(policy=AssetAccessPolicy(preferred_schemes=("https", "s3")))
        .resolve(_asset(primary, alternates=MappingProxyType({"s3": alternate})))
        .location
    )
    assert location is primary


def test_filters_unsupported_combinations_before_checking_ambiguity() -> None:
    compatible = StorageScheme(known_type=KnownStorageType.AWS_S3, region="us-west-2")
    incompatible = StorageScheme(known_type=KnownStorageType.GOOGLE_CLOUD_STORAGE)
    s3_auth = AuthenticationScheme(known_type=KnownAuthenticationType.S3)
    unsupported_auth = AuthenticationScheme(known_type=KnownAuthenticationType.OAUTH2)
    asset = _asset(
        AssetLocation(
            "s3://bucket/a%20b.tif",
            {"wrong": incompatible, "correct": compatible},
            {"oauth": unsupported_auth, "aws": s3_auth},
        )
    )
    provider = AsyncMock(side_effect=AssertionError("resolve must not fetch credentials"))
    client = Client(s3_credentials={"aws": provider})
    resolved = client.resolve(asset)
    assert resolved.storage_scheme is compatible
    assert resolved.authentication_scheme is s3_auth
    assert resolved.path == "a b.tif"

    # A rejected preferred location still permits a supported alternate.
    fallback = AssetLocation("https://example.com/a.tif")
    assert Client().resolve(replace(asset, alternates={"http": fallback})).location is fallback


@pytest.mark.parametrize(
    "href", ["file:///tmp/a", "gs://bucket/a", "az://account/container/a", "https://example.com/a"]
)
def test_s3_authentication_is_not_accepted_by_other_backends(href: str) -> None:
    auth = AuthenticationScheme(known_type=KnownAuthenticationType.S3)
    with pytest.raises(ValueError, match="unsupported"):
        Client().resolve(_asset(AssetLocation(href, authentication_schemes={"aws": auth})))


@pytest.fixture
def object_server() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append({"path": self.path, "headers": self.headers})
            body = b"0123456789"
            byte_range = self.headers.get("Range")
            self.send_response(206 if byte_range else 200)
            if byte_range:
                start, end = map(int, byte_range.removeprefix("bytes=").split("-"))
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(body)}")
                body = body[start : end + 1]
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", '"test"')
            self.send_header("Last-Modified", "Mon, 12 Oct 2026 12:00:00 GMT")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.asyncio
async def test_http_paths_queries_and_ranges(object_server: tuple[str, list[dict[str, Any]]]) -> None:
    origin, requests = object_server
    client = Client()
    asset = _asset(AssetLocation(f"{origin}/folder/a%20b%25.tif?versionId=abc%2Fdef&download=1"))
    assert await client.read_bytes(asset) == b"0123456789"
    resolved = client.resolve(asset)
    assert resolved.path == "folder/a b%.tif"
    assert bytes(await obstore.get_range_async(resolved.store, resolved.path, start=2, end=6)) == b"2345"
    assert [request["path"] for request in requests] == [
        "/folder/a%20b%25.tif?versionId=abc%2Fdef&download=1",
        "/folder/a%20b%25.tif?versionId=abc%2Fdef&download=1",
    ]
    other_version = _asset(AssetLocation(f"{origin}/folder/a%20b%25.tif?versionId=other"))
    assert client.resolve(other_version).store is not resolved.store


@pytest.mark.asyncio
async def test_cloud_authentication_is_explicit(
    object_server: tuple[str, list[dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, requests = object_server
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ambient-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "ambient-secret")
    monkeypatch.setenv("AZURE_STORAGE_SAS_TOKEN", "sig=ambient&se=2099-01-01")

    def local_s3(bucket: str, **kwargs: Any) -> S3Store:
        kwargs["aws_endpoint_url_s3"] = origin
        return S3Store(bucket, client_options={"allow_http": True}, **kwargs)

    def local_azure(container: str, **kwargs: Any) -> AzureStore:
        kwargs["endpoint"] = origin
        return AzureStore(container, client_options={"allow_http": True}, **kwargs)

    def local_gcs(bucket: str, **kwargs: Any) -> GCSStore:
        return GCSStore(bucket, base_url=origin, client_options={"allow_http": True}, **kwargs)

    monkeypatch.setattr(obstore.store, "S3Store", local_s3)
    monkeypatch.setattr(obstore.store, "AzureStore", local_azure)
    monkeypatch.setattr(obstore.store, "GCSStore", local_gcs)
    client = Client()
    for href in ("s3://bucket/a%20b", "gs://bucket/a%20b", "az://account/container/a%20b"):
        assert await client.read_bytes(_asset(AssetLocation(href))) == b"0123456789"
    assert all("Authorization" not in request["headers"] and "?" not in request["path"] for request in requests)

    auth = AuthenticationScheme(known_type=KnownAuthenticationType.S3)
    storage = StorageScheme(known_type=KnownStorageType.AWS_S3, region="us-west-2", requester_pays=True)
    asset = _asset(AssetLocation("s3://bucket/a%20b", {"aws": storage}, {"aws": auth}))
    with pytest.raises(ValueError, match="explicitly configured credential provider"):
        client.resolve(asset)

    async def credentials() -> "S3Credential":
        return {
            "access_key_id": "explicit-key",
            "secret_access_key": "explicit-secret",
            "token": "session",
            "expires_at": None,
        }

    async def other_credentials() -> "S3Credential":
        return {"access_key_id": "other-key", "secret_access_key": "other-secret", "token": None, "expires_at": None}

    providers = {"aws": credentials, "alias": credentials, "other": other_credentials}
    client = Client(s3_credentials=providers)
    providers["aws"] = other_credentials  # Existing clients retain their credential bindings.
    resolved = client.resolve(asset)
    anonymous = replace(asset, primary=replace(asset.primary, authentication_schemes={}))
    other = replace(asset, primary=replace(asset.primary, authentication_schemes={"other": auth}))
    alias = replace(asset, primary=replace(asset.primary, authentication_schemes={"alias": auth}))
    assert client.resolve(anonymous).store is not resolved.store
    assert client.resolve(other).store is not resolved.store
    assert client.resolve(alias).store is resolved.store
    assert await client.read_bytes(asset) == b"0123456789"
    headers = requests[-1]["headers"]
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=explicit-key/")
    assert headers["x-amz-security-token"] == "session"
    assert headers["x-amz-request-payer"] == "requester"
    assert await Client(s3_credentials=providers).read_bytes(asset) == b"0123456789"
    assert requests[-1]["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=other-key/")


@pytest.mark.asyncio
async def test_read_stream_and_atomic_download(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"asset contents")
    asset = _asset(AssetLocation(source.as_uri()))
    client = Client()

    assert await client.read_bytes(asset) == b"asset contents"
    with pytest.raises(ValueError, match="max_bytes=5"):
        await client.read_bytes(asset, max_bytes=5)
    assert b"".join([chunk async for chunk in client.iter_bytes(asset)]) == b"asset contents"

    destination = tmp_path / "nested" / "destination.bin"
    assert await client.download(asset, destination) == destination
    assert destination.read_bytes() == b"asset contents"
    with pytest.raises(FileExistsError):
        await client.download(asset, destination)
    source.write_bytes(b"replacement")
    await client.download(asset, destination, overwrite=True)
    assert destination.read_bytes() == b"replacement"
    assert list(destination.parent.glob("*.tmp")) == []


@pytest.mark.asyncio
async def test_open_geotiff_forwards_resolved_store_path_and_options(tmp_path: Path) -> None:
    path = tmp_path / "data.tif"
    path.touch()
    asset = _asset(AssetLocation(path.as_uri()), media_type="image/tiff; application=geotiff")
    opened = object()
    with patch("async_geotiff.GeoTIFF.open", new=AsyncMock(return_value=opened)) as open_mock:
        result = await Client().open_geotiff(asset, prefetch=1024, multiplier=3)

    assert result is opened
    args, kwargs = open_mock.call_args
    assert args == (str(path).lstrip("/"),)
    assert isinstance(kwargs["store"], LocalStore)
    assert kwargs["prefetch"] == 1024
    assert kwargs["multiplier"] == 3


@pytest.mark.asyncio
async def test_open_geotiff_rejects_incompatible_media_type() -> None:
    asset = _asset(AssetLocation("file:///tmp/data.json"), media_type="application/json")
    with pytest.raises(ValueError, match="not compatible"):
        await Client().open_geotiff(asset)
