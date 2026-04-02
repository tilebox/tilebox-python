import re
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
import responses
from hypothesis import HealthCheck, given, settings
from obstore.store import LocalStore

from tests.storage_data import ers_granules, landsat_granules, s5p_granules, umbra_granules
from tilebox.storage.aio import (
    ASFStorageClient,
    CopernicusStorageClient,
    UmbraStorageClient,
    USGSLandsatStorageClient,
    _HttpClient,
    list_object_paths,
)
from tilebox.storage.granule import (
    ASFStorageGranule,
    CopernicusStorageGranule,
    UmbraStorageGranule,
    USGSLandsatStorageGranule,
)

pytestmark = pytest.mark.usefixtures("responses_mock")

ASF_LOGIN_URL = "https://urs.earthdata.nasa.gov/oauth/authorize"


def _mock_asf_login(*, status: int = 200) -> None:
    responses.add(responses.GET, ASF_LOGIN_URL, status=status)


def _count_calls(url: str) -> int:
    return sum(call.request.url == url for call in responses.calls)


def _count_calls_by_prefix(url: str) -> int:
    return sum(str(call.request.url).startswith(url) for call in responses.calls)


@pytest.mark.asyncio
async def test_client_login() -> None:
    _mock_asf_login()
    client = _HttpClient(auth={"ASF": ("username", "password")})
    fresh = await client._client("ASF")
    cached = await client._client("ASF")

    assert isinstance(fresh, type(cached))
    assert fresh is cached
    assert _count_calls_by_prefix(ASF_LOGIN_URL) == 1

    await fresh.close()


@pytest.mark.asyncio
async def test_client_login_failed() -> None:
    _mock_asf_login(status=401)
    client = _HttpClient(auth={"ASF": ("invalid-username", "password")})
    with pytest.raises(ValueError, match=re.escape("Invalid username or password.")):
        await client._client("ASF")


@pytest.mark.asyncio
async def test_client_missing_credentials() -> None:
    client = _HttpClient(auth={})
    with pytest.raises(ValueError, match=r"Missing credentials.*"):
        await client._client("ASF")


@pytest.mark.asyncio
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download_quicklook(
    tmp_path: Path,
    granule: ASFStorageGranule,
) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    _mock_asf_login()
    responses.add(responses.GET, granule.urls.quicklook, body=b"my-quicklook-image")

    client = _HttpClient(auth={"ASF": ("username", "password")})
    downloaded = await client.download_quicklook(granule, tmp_path)
    expected = tmp_path / granule.urls.quicklook.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"my-quicklook-image"


@pytest.mark.asyncio
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_quicklook(
    granule: ASFStorageGranule,
) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    _mock_asf_login()
    responses.add(responses.GET, granule.urls.quicklook, body=b"my-quicklook-image")

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
async def test_download(
    tmp_path: Path,
    granule: ASFStorageGranule,
) -> None:
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    _mock_asf_login()
    responses.add(responses.GET, granule.urls.data, body="".join(mock_data).encode())

    client = _HttpClient(auth={"ASF": ("username", "password")})
    downloaded = await client.download(granule, tmp_path, extract=False, show_progress=False)
    expected = tmp_path / granule.urls.data.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert expected.exists()
    assert expected.read_bytes() == "".join(mock_data).encode()


@pytest.mark.asyncio
@given(ers_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download_verify_md5(
    tmp_path: Path,
    granule: ASFStorageGranule,
) -> None:
    _mock_asf_login()
    responses.add(responses.GET, granule.urls.data, body=b"my-granule")

    client = _HttpClient(auth={"ASF": ("username", "password")})
    with pytest.raises(ValueError, match=r".*md5sum mismatch.*"):
        await client.download(granule, tmp_path, extract=False, show_progress=False)


@pytest.mark.asyncio
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download_quicklook(
    tmp_path: Path,
    granule: ASFStorageGranule,
) -> None:
    assert granule.urls.quicklook is not None  # for type checker

    _mock_asf_login()
    responses.add(responses.GET, granule.urls.quicklook, body=b"my-quicklook-image")

    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download_quicklook(granule)
    expected = tmp_path / "ASF" / granule.granule_name / granule.urls.quicklook.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"my-quicklook-image"

    for _ in range(10):
        await client.download_quicklook(granule)
    assert _count_calls(granule.urls.quicklook) == 1


@pytest.mark.asyncio
@given(ers_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download(
    tmp_path: Path,
    granule: ASFStorageGranule,
) -> None:
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    _mock_asf_login()
    responses.add(responses.GET, granule.urls.data, body="".join(mock_data).encode())

    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download(granule, extract=False, show_progress=False)
    expected = tmp_path / "ASF" / granule.granule_name / granule.urls.data.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert expected.exists()
    assert expected.read_bytes() == "".join(mock_data).encode()

    for _ in range(10):
        await client.download(granule, extract=False, show_progress=False)
    assert _count_calls(granule.urls.data) == 1


@pytest.mark.asyncio
async def test_list_object_paths() -> None:
    with TemporaryDirectory() as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async("prefix/object1", b"content1")
        await store.put_async("prefix/object2", b"content2")
        await store.put_async("prefix/subdir/object3", b"content3")

        objects = await list_object_paths(store, "prefix")
        # we always need a forward slash in our paths, even on windows
        assert objects == ["object1", "object2", "subdir/object3"]


@pytest.mark.asyncio
@given(umbra_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_umbra_storage_client_download(granule: UmbraStorageGranule) -> None:
    with TemporaryDirectory() as tmp_path:
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
    with TemporaryDirectory() as tmp_path:
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
    with TemporaryDirectory() as tmp_path:
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
    with TemporaryDirectory() as tmp_path:
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
    with TemporaryDirectory() as tmp_path:
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
    with TemporaryDirectory() as tmp_path:
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
    with TemporaryDirectory() as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/{granule.granule_name}", b"content1"
        )
        with patch("tilebox.storage.aio.S3Store") as store_mock, patch("tilebox.storage.aio.Boto3CredentialProvider"):
            store_mock.return_value = store
            landsat = USGSLandsatStorageClient(cache_directory=Path(tmp_path))

        folder = await landsat.download(granule, show_progress=False)
        assert folder.exists()
        assert (folder / granule.granule_name).read_bytes() == b"content1"


@pytest.mark.asyncio
@given(landsat_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_landsat_storage_client_list_objects(granule: USGSLandsatStorageGranule) -> None:
    with TemporaryDirectory() as tmp_path:
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
        with patch("tilebox.storage.aio.S3Store") as store_mock, patch("tilebox.storage.aio.Boto3CredentialProvider"):
            store_mock.return_value = store
            landsat = USGSLandsatStorageClient(cache_directory=Path(tmp_path))

        objects = await landsat.list_objects(granule)
        assert len(objects) == 2
        assert sorted(objects) == sorted([granule.granule_name, f"{granule.granule_name}_thumb_small.jpeg"])


@pytest.mark.asyncio
@given(landsat_granules())
@settings(max_examples=1, deadline=timedelta(milliseconds=100))
async def test_landsat_storage_client_download_objects(granule: USGSLandsatStorageGranule) -> None:
    with TemporaryDirectory() as tmp_path:
        store_path = Path(tmp_path) / "store"
        store_path.mkdir(exist_ok=True, parents=True)
        store = LocalStore(store_path)

        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/{granule.granule_name}", b"content1"
        )
        await store.put_async(
            f"{granule.location.removeprefix('s3://usgs-landsat/')}/other_product_{granule.granule_name}", b"content2"
        )
        with patch("tilebox.storage.aio.S3Store") as store_mock, patch("tilebox.storage.aio.Boto3CredentialProvider"):
            store_mock.return_value = store
            landsat = USGSLandsatStorageClient(cache_directory=Path(tmp_path))

        folder = await landsat.download_objects(granule, [granule.granule_name], show_progress=False)
        assert folder.exists()
        assert (folder / granule.granule_name).read_bytes() == b"content1"
        assert not (folder / f"other_product_{granule.granule_name}").exists()
