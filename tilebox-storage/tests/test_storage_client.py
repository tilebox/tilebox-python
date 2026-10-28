import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from obstore.store import LocalStore
from pyqwest import Request

import tilebox.storage.aio as storage_aio
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

# Warm lazy storage attributes used in Hypothesis-timed tests. Otherwise the first generated example pays the one-time
# import cost and Hypothesis can report flaky deadline failures when replayed examples are much faster.
_ = storage_aio.Boto3CredentialProvider
_ = storage_aio.S3Store

pytestmark = pytest.mark.usefixtures("http_responses")

ASF_LOGIN_URL = "https://urs.earthdata.nasa.gov/oauth/authorize"


def test_heavy_imports_are_lazy() -> None:
    code = (
        "import inspect\n"
        "import pickle\n"
        "import sys\n"
        "import tilebox.storage as storage\n"
        "heavy = {'tilebox.storage.aio', 'xarray', 'obstore', 'pyqwest', 'IPython'}\n"
        "assert not heavy & sys.modules.keys()\n"
        "assert set(storage.__all__) <= set(dir(storage))\n"
        "client = storage.LocalFileSystemStorageClient\n"
        "assert storage.LocalFileSystemStorageClient is client\n"
        "assert inspect.isclass(client)\n"
        "assert client.__module__ == 'tilebox.storage'\n"
        "assert client.__init__.__qualname__ == 'LocalFileSystemStorageClient.__init__'\n"
        "assert pickle.loads(pickle.dumps(client)) is client\n"
        "assert 'tilebox.storage.aio' in sys.modules\n"
        "assert not {'xarray', 'obstore', 'pyqwest', 'IPython'} & sys.modules.keys()\n"
        "try:\n"
        "    from tilebox.storage.aio import Image\n"
        "except ImportError:\n"
        "    pass\n"
        "else:\n"
        "    assert inspect.isclass(Image)\n"
        "    assert 'IPython' in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603


@pytest.mark.asyncio
async def test_client_login(http_requests: list[Request]) -> None:
    client = _HttpClient(auth={"ASF": ("username", "password")})
    await client._client("ASF")
    await client._client("ASF")
    assert sum(request.url.startswith(ASF_LOGIN_URL) for request in http_requests) == 1
    await client.close()


@pytest.mark.asyncio
async def test_client_login_failed(http_responses: dict[str, tuple[int, bytes]]) -> None:
    http_responses[ASF_LOGIN_URL] = (401, b"")
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
    http_responses: dict[str, tuple[int, bytes]],
    granule: ASFStorageGranule,
) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    http_responses[granule.urls.quicklook] = (200, b"my-quicklook-image")

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
    http_responses: dict[str, tuple[int, bytes]],
    granule: ASFStorageGranule,
) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    http_responses[granule.urls.quicklook] = (200, b"my-quicklook-image")

    client = _HttpClient(auth={"ASF": ("username", "password")})
    with patch("tilebox.storage.aio._display_quicklook") as display_mock:
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
    http_responses: dict[str, tuple[int, bytes]],
    granule: ASFStorageGranule,
) -> None:
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    http_responses[granule.urls.data] = (200, "".join(mock_data).encode())

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
    http_responses: dict[str, tuple[int, bytes]],
    granule: ASFStorageGranule,
) -> None:
    http_responses[granule.urls.data] = (200, b"my-granule")

    client = _HttpClient(auth={"ASF": ("username", "password")})
    with pytest.raises(ValueError, match=r".*md5sum mismatch.*"):
        await client.download(granule, tmp_path, extract=False, show_progress=False)


@pytest.mark.asyncio
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download_quicklook(
    tmp_path: Path,
    http_responses: dict[str, tuple[int, bytes]],
    http_requests: list[Request],
    granule: ASFStorageGranule,
) -> None:
    assert granule.urls.quicklook is not None  # for type checker

    http_responses[granule.urls.quicklook] = (200, b"my-quicklook-image")

    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download_quicklook(granule)
    expected = tmp_path / "ASF" / granule.granule_name / granule.urls.quicklook.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"my-quicklook-image"

    for _ in range(10):
        await client.download_quicklook(granule)
    assert sum(request.url == granule.urls.quicklook for request in http_requests) == 1


@pytest.mark.asyncio
@given(ers_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download(
    tmp_path: Path,
    http_responses: dict[str, tuple[int, bytes]],
    http_requests: list[Request],
    granule: ASFStorageGranule,
) -> None:
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    http_responses[granule.urls.data] = (200, "".join(mock_data).encode())

    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download(granule, extract=False, show_progress=False)
    expected = tmp_path / "ASF" / granule.granule_name / granule.urls.data.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert expected.exists()
    assert expected.read_bytes() == "".join(mock_data).encode()

    for _ in range(10):
        await client.download(granule, extract=False, show_progress=False)
    assert sum(request.url == granule.urls.data for request in http_requests) == 1


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

        with patch("obstore.store.S3Store") as store_mock:
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

        with patch("obstore.store.S3Store") as store_mock:
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

        with patch("obstore.store.S3Store") as store_mock:
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
        with patch("obstore.store.S3Store") as store_mock:
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
@pytest.mark.parametrize(("status", "body"), [(200, b"thumbnail"), (200, b""), (403, b"secret")])
async def test_copernicus_http_quicklook(
    tmp_path: Path, http_responses: dict[str, tuple[int, bytes]], status: int, body: bytes
) -> None:
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Assets(scene)/$value"
    granule = CopernicusStorageGranule(datetime(2026, 10, 28), "scene", "/eodata/Sentinel-2/scene", url)
    http_responses[url] = (status, body)
    client = CopernicusStorageClient("access", "secret", cache_directory=tmp_path)
    expected = tmp_path / "CopernicusDataspace" / "Sentinel-2" / "scene" / "scene.jpg"
    if status == 200 and body:
        assert await client.download_quicklook(granule) == expected
        assert expected.read_bytes() == body
    else:
        with pytest.raises(ValueError, match="HTTP 403" if status == 403 else "empty content") as error:
            await client.download_quicklook(granule)
        assert "secret" not in str(error.value)
        assert not expected.exists()


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
        with patch("obstore.store.S3Store") as store_mock:
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
        with patch("obstore.store.S3Store") as store_mock:
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
        with patch("obstore.store.S3Store") as store_mock, patch("obstore.auth.boto3.Boto3CredentialProvider"):
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
        with patch("obstore.store.S3Store") as store_mock, patch("obstore.auth.boto3.Boto3CredentialProvider"):
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
        with patch("obstore.store.S3Store") as store_mock, patch("obstore.auth.boto3.Boto3CredentialProvider"):
            store_mock.return_value = store
            landsat = USGSLandsatStorageClient(cache_directory=Path(tmp_path))

        folder = await landsat.download_objects(granule, [granule.granule_name], show_progress=False)
        assert folder.exists()
        assert (folder / granule.granule_name).read_bytes() == b"content1"
        assert not (folder / f"other_product_{granule.granule_name}").exists()
