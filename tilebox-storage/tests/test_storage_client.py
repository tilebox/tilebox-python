from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from hypothesis import HealthCheck, given, settings
from obstore.store import LocalStore
from pytest_httpx import HTTPXMock, IteratorStream

from tests.storage_data import ers_granules, landsat_granules, s5p_granules, umbra_granules
from tilebox.storage.aio import (
    ASFStorageClient,
    CopernicusStorageClient,
    UmbraStorageClient,
    USGSLandsatStorageClient,
    _HttpClient,
)
from tilebox.storage.granule import (
    ASFStorageGranule,
    CopernicusStorageGranule,
    UmbraStorageGranule,
    USGSLandsatStorageGranule,
)


@pytest.mark.asyncio
async def test_client_login(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response()
    client = _HttpClient(auth={"ASF": ("username", "password")})
    await client._client("ASF")
    assert isinstance(client._clients["ASF"], AsyncClient)


@pytest.mark.asyncio
async def test_client_login_failed(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(401)
    client = _HttpClient(auth={"ASF": ("invalid-username", "password")})
    with pytest.raises(ValueError, match="Invalid username or password."):
        await client._client("ASF")


@pytest.mark.asyncio
async def test_client_missing_credentials() -> None:
    client = _HttpClient(auth={})
    with pytest.raises(ValueError, match="Missing credentials.*"):
        await client._client("ASF")


@pytest.mark.asyncio
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download_quicklook(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    httpx_mock.add_response(content=b"login-response")
    httpx_mock.add_response(content=b"my-quicklook-image")
    client = _HttpClient(auth={"ASF": ("username", "password")})
    downloaded = await client.download_quicklook(granule, tmp_path)
    expected = tmp_path / granule.urls.quicklook.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"my-quicklook-image"


@pytest.mark.asyncio
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_quicklook(httpx_mock: HTTPXMock, granule: ASFStorageGranule) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    httpx_mock.add_response(content=b"login-response")
    httpx_mock.add_response(content=b"my-quicklook-image")
    client = _HttpClient(auth={"ASF": ("username", "password")})
    with patch("tilebox.storage.aio.Image"), patch("tilebox.storage.aio._display_quicklook") as display_mock:
        await client.quicklook(granule)
        display_mock.assert_called_once()
        assert display_mock.call_args[0][0] == b"my-quicklook-image"
        img_name = granule.urls.quicklook.rsplit("/", 1)[-1]
        assert display_mock.call_args[0][-1].startswith(f"<code>Image {img_name} © ASF")


@pytest.mark.asyncio
@given(ers_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    httpx_mock.add_response(content=b"login-response")
    httpx_mock.add_response(stream=IteratorStream([d.encode() for d in mock_data]))
    client = _HttpClient(auth={"ASF": ("username", "password")})
    downloaded = await client.download(granule, tmp_path, extract=False, show_progress=False)
    expected = tmp_path / granule.urls.data.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert expected.exists()
    assert expected.read_bytes() == "".join(mock_data).encode()


@pytest.mark.asyncio
@given(ers_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download_verify_md5(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    httpx_mock.add_response(content=b"login-response")
    httpx_mock.add_response(stream=IteratorStream([b"my-granule"]))
    client = _HttpClient(auth={"ASF": ("username", "password")})
    with pytest.raises(ValueError, match=".*md5sum mismatch.*"):
        await client.download(granule, tmp_path, extract=False, show_progress=False)


@pytest.mark.asyncio
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download_quicklook(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    assert granule.urls.quicklook is not None  # for type checker

    httpx_mock.reset()  # so we get an accurate request count below
    httpx_mock.add_response(content=b"login-response")
    httpx_mock.add_response(content=b"my-quicklook-image")
    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download_quicklook(granule)
    expected = tmp_path / "ASF" / granule.granule_name / granule.urls.quicklook.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"my-quicklook-image"

    for _ in range(10):
        await client.download_quicklook(granule)
    assert len(httpx_mock.get_requests(url=granule.urls.quicklook)) == 1


@pytest.mark.asyncio
@given(ers_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    httpx_mock.reset()  # so we get an accurate request count below
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    httpx_mock.add_response(content=b"login-response")
    httpx_mock.add_response(stream=IteratorStream([d.encode() for d in mock_data]))
    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download(granule, extract=False, show_progress=False)
    expected = tmp_path / "ASF" / granule.granule_name / granule.urls.data.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert expected.exists()
    assert expected.read_bytes() == "".join(mock_data).encode()

    for _ in range(10):
        await client.download(granule, extract=False, show_progress=False)
    assert len(httpx_mock.get_requests(url=granule.urls.data)) == 1


@pytest.mark.asyncio
@given(umbra_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_umbra_storage_client_download(granule: UmbraStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(f"sar-data/tasks/{granule.location}/{granule.granule_name}_GEC.tif", b"content1")
        await store.put_async(f"sar-data/tasks/{granule.location}/{granule.granule_name}_CPHD.cphd", b"content2")

        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            umbra = UmbraStorageClient(Path(tmp_path) / "cache")

        folder = await umbra.download(granule, show_progress=False)
        assert folder.exists()
        assert folder.parent.parent.parent == Path(tmp_path) / "cache" / "Umbra" / "sar-data" / "tasks"
        assert (folder / f"{granule.granule_name}_GEC.tif").read_bytes() == b"content1"
        assert (folder / f"{granule.granule_name}_CPHD.cphd").read_bytes() == b"content2"


@pytest.mark.asyncio
@given(umbra_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_umbra_storage_client_list_objects(granule: UmbraStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(f"sar-data/tasks/{granule.location}/{granule.granule_name}_GEC.tif", b"content1")
        await store.put_async(f"sar-data/tasks/{granule.location}/{granule.granule_name}_CPHD.cphd", b"content2")
        await store.put_async(
            f"sar-data/tasks/another_{granule.location}/another_{granule.granule_name}_CPHD.cphd", b"content2"
        )

        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            umbra = UmbraStorageClient(Path(tmp_path) / "cache")

        objects = await umbra.list_objects(granule)
        assert sorted(objects) == sorted([f"{granule.granule_name}_GEC.tif", f"{granule.granule_name}_CPHD.cphd"])


@pytest.mark.asyncio
@given(umbra_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_umbra_storage_client_download_objects(granule: UmbraStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(f"sar-data/tasks/{granule.location}/{granule.granule_name}_GEC.tif", b"content1")
        await store.put_async(f"sar-data/tasks/{granule.location}/{granule.granule_name}_CPHD.cphd", b"content2")

        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            umbra = UmbraStorageClient(Path(tmp_path) / "cache")

        folder = await umbra.download_objects(granule, [f"{granule.granule_name}_GEC.tif"], show_progress=False)
        assert (folder / f"{granule.granule_name}_GEC.tif").read_bytes() == b"content1"
        assert not (folder / f"{granule.granule_name}_CPHD.cphd").exists()


@pytest.mark.asyncio
@given(s5p_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_copernicus_storage_client_download(granule: CopernicusStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(f"{granule.location.removeprefix('/eodata/')}/{granule.granule_name}", b"content1")
        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            copernicus = CopernicusStorageClient(
                access_key="testing",
                secret_access_key="testing",  # noqa: S106
                cache_directory=Path(tmp_path),
            )

        folder = await copernicus.download(granule, show_progress=False)
        assert folder.exists()
        assert (folder / granule.granule_name).read_bytes() == b"content1"


@pytest.mark.asyncio
@given(s5p_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_copernicus_storage_client_list_objects(granule: CopernicusStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(f"{granule.location.removeprefix('/eodata/')}/{granule.granule_name}", b"content1")
        await store.put_async(
            f"{granule.location.removeprefix('/eodata/')}_other_granule/{granule.granule_name}", b"content2"
        )
        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            copernicus = CopernicusStorageClient(
                access_key="testing",
                secret_access_key="testing",  # noqa: S106
                cache_directory=Path(tmp_path),
            )

        objects = await copernicus.list_objects(granule)
        assert len(objects) == 1
        assert objects[0] == granule.granule_name


@pytest.mark.asyncio
@given(s5p_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_copernicus_storage_client_download_objects(granule: CopernicusStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(f"{granule.location.removeprefix('/eodata/')}/{granule.granule_name}", b"content1")
        await store.put_async(
            f"{granule.location.removeprefix('/eodata/')}/other_product_{granule.granule_name}", b"content2"
        )
        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            copernicus = CopernicusStorageClient(
                access_key="testing",
                secret_access_key="testing",  # noqa: S106
                cache_directory=Path(tmp_path),
            )
        folder = await copernicus.download_objects(granule, [granule.granule_name], show_progress=False)
        assert folder.exists()
        assert (folder / granule.granule_name).read_bytes() == b"content1"
        assert not (folder / f"other_product_{granule.granule_name}").exists()


@pytest.mark.asyncio
@given(landsat_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_landsat_storage_client_download(granule: USGSLandsatStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/{granule.granule_name}", b"content1"
        )
        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            landsat = USGSLandsatStorageClient(cache_directory=Path(tmp_path))

        folder = await landsat.download(granule, show_progress=False)
        assert folder.exists()
        assert (folder / granule.granule_name).read_bytes() == b"content1"


@pytest.mark.asyncio
@given(landsat_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_landsat_storage_client_list_objects(granule: USGSLandsatStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/{granule.granule_name}", b"content1"
        )
        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/{granule.granule_name}_thumb_small.jpeg",
            b"content2",
        )
        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            landsat = USGSLandsatStorageClient(cache_directory=Path(tmp_path))

        objects = await landsat.list_objects(granule)
        assert len(objects) == 2
        assert sorted(objects) == sorted([granule.granule_name, f"{granule.granule_name}_thumb_small.jpeg"])


@pytest.mark.asyncio
@given(landsat_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_landsat_storage_client_download_objects(granule: USGSLandsatStorageGranule) -> None:
    with TemporaryDirectory(delete=True) as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/{granule.granule_name}", b"content1"
        )
        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/other_product_{granule.granule_name}", b"content2"
        )
        with patch("tilebox.storage.aio.S3Store") as store_mock:
            store_mock.return_value = store
            landsat = USGSLandsatStorageClient(cache_directory=Path(tmp_path))

        folder = await landsat.download_objects(granule, [granule.granule_name], show_progress=False)
        assert folder.exists()
        assert (folder / granule.granule_name).read_bytes() == b"content1"
        assert not (folder / f"other_product_{granule.granule_name}").exists()
