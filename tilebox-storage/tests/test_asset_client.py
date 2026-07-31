import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from obstore.store import LocalStore

from tilebox.datasets.assets.assets import Asset, AssetLocation
from tilebox.datasets.datasets.stac.v1.authentication_pb import AuthenticationScheme, KnownAuthenticationType
from tilebox.datasets.datasets.stac.v1.storage_pb import KnownStorageType, StorageScheme
from tilebox.storage.aio import AssetAccessPolicy, Client


def _asset(location: AssetLocation, **kwargs: Any) -> Asset:
    return Asset(key="data", primary=location, **kwargs)


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
            MappingProxyType({"oauth": auth}),
        )
    )
    client = Client()

    with pytest.raises(ValueError, match=r"primary.*multiple storage schemes"):
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
@pytest.mark.skipif(sys.version_info < (3, 11), reason="async-geotiff requires Python 3.11 or newer")
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
@pytest.mark.skipif(sys.version_info < (3, 11), reason="async-geotiff requires Python 3.11 or newer")
async def test_open_geotiff_rejects_incompatible_media_type() -> None:
    asset = _asset(AssetLocation("file:///tmp/data.json"), media_type="application/json")
    with pytest.raises(ValueError, match="not compatible"):
        await Client().open_geotiff(asset)
