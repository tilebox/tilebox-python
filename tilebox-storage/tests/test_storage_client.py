import os
import shutil
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from httpx import AsyncClient
from hypothesis import HealthCheck, given, settings
from moto import mock_aws
from mypy_boto3_s3 import S3Client
from pytest_httpx import HTTPXMock, IteratorStream

from tests.storage_data import asf_granules, ers_granules, s5p_granules, umbra_granules
from tilebox.storage.aio import ASFStorageClient, CopernicusStorageClient, UmbraStorageClient, _HttpClient, _S3Client
from tilebox.storage.granule import ASFStorageGranule, CopernicusStorageGranule, UmbraStorageGranule


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
# ^^^ see https://medium.com/@BartekSkwira/how-to-solve-pytest-pytestunraisableexceptionwarning-8d75a4d1f801
async def test_client_login(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response()
    client = _HttpClient(auth={"ASF": ("username", "password")})
    await client._client("ASF")
    assert isinstance(client._clients["ASF"], AsyncClient)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
# ^^^ see https://medium.com/@BartekSkwira/how-to-solve-pytest-pytestunraisableexceptionwarning-8d75a4d1f801
async def test_client_login_failed(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(401)
    client = _HttpClient(auth={"ASF": ("invalid-username", "password")})
    with pytest.raises(ValueError, match="Invalid username or password."):
        await client._client("ASF")


@pytest.mark.asyncio()
async def test_client_missing_credentials() -> None:
    client = _HttpClient(auth={})
    with pytest.raises(ValueError, match="Missing credentials.*"):
        await client._client("ASF")


@pytest.mark.asyncio()
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download_quicklook(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    httpx_mock.add_response(content=b"my-quicklook-image")
    client = _HttpClient(auth={"ASF": ("username", "password")})
    downloaded = await client.download_quicklook(granule, tmp_path)
    expected = tmp_path / granule.urls.quicklook.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"my-quicklook-image"


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_quicklook(httpx_mock: HTTPXMock, granule: ASFStorageGranule) -> None:
    assert granule.urls.quicklook is not None  # for type checker
    httpx_mock.add_response(content=b"my-quicklook-image")
    client = _HttpClient(auth={"ASF": ("username", "password")})
    with patch("tilebox.storage.aio.Image"), patch("tilebox.storage.aio._display_quicklook") as display_mock:
        await client.quicklook(granule)
        display_mock.assert_called_once()
        assert display_mock.call_args[0][0] == b"my-quicklook-image"
        assert display_mock.call_args[0][1] == granule.urls.quicklook.rsplit("/", 1)[-1]


@pytest.mark.asyncio()
@given(asf_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    httpx_mock.add_response(stream=IteratorStream([d.encode() for d in mock_data]))
    client = _HttpClient(auth={"ASF": ("username", "password")})
    downloaded = await client.download(granule, tmp_path, extract=False, show_progress=False)
    expected = tmp_path / granule.urls.data.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert expected.exists()
    assert expected.read_bytes() == "".join(mock_data).encode()


@pytest.mark.asyncio()
@given(asf_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_download_verify_md5(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    httpx_mock.add_response(stream=IteratorStream([b"my-granule"]))
    client = _HttpClient(auth={"ASF": ("username", "password")})
    with pytest.raises(ValueError, match=".*md5sum mismatch.*"):
        await client.download(granule, tmp_path, extract=False, show_progress=False)


@pytest.mark.asyncio()
@given(ers_granules(ensure_quicklook=True))
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download_quicklook(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    assert granule.urls.quicklook is not None  # for type checker

    httpx_mock.reset(True)  # so we get an accurate request count below
    httpx_mock.add_response(content=b"my-quicklook-image")
    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download_quicklook(granule)
    expected = tmp_path / granule.storage_provider / granule.granule_name / granule.urls.quicklook.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"my-quicklook-image"

    for _ in range(10):
        await client.download_quicklook(granule)
    assert len(httpx_mock.get_requests(url=granule.urls.quicklook)) == 1


@pytest.mark.asyncio()
@given(asf_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_cached_download(httpx_mock: HTTPXMock, tmp_path: Path, granule: ASFStorageGranule) -> None:
    httpx_mock.reset(True)  # so we get an accurate request count below
    mock_data = ["my-granule", "some-data", "some-more-data"]
    granule.md5sum = "1c3cd9bf5dd29c2a79d4783ca2aee55e"  # real md5sum of the above data
    httpx_mock.add_response(stream=IteratorStream([d.encode() for d in mock_data]))
    client = ASFStorageClient("username", "password", cache_directory=tmp_path)
    downloaded = await client.download(granule, extract=False, show_progress=False)
    expected = tmp_path / granule.storage_provider / granule.granule_name / granule.urls.data.rsplit("/", 1)[-1]
    assert downloaded == expected
    assert expected.exists()
    assert expected.read_bytes() == "".join(mock_data).encode()

    for _ in range(10):
        await client.download(granule, extract=False, show_progress=False)
    assert len(httpx_mock.get_requests(url=granule.urls.data)) == 1


@pytest.fixture()
def _aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_SECURITY_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_SESSION_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    # See http://docs.getmoto.org/en/latest/docs/services/s3.html
    os.environ["MOTO_S3_CUSTOM_ENDPOINTS"] = CopernicusStorageClient._ENDPOINT_URL


@pytest.fixture()
def aws(_aws_credentials: None) -> Iterator[S3Client]:
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_list_objects(aws: S3Client) -> None:
    bucket = "bucket1"
    aws.create_bucket(Bucket=bucket)
    aws.put_object(Bucket=bucket, Key="test1", Body=b"content1")

    s3 = _S3Client(aws, bucket)

    res = list(s3.list_objects("test1"))
    assert len(res) == 1
    assert "Key" in res[0]
    assert res[0]["Key"] == "test1"
    assert "Size" in res[0]
    assert res[0]["Size"] == len(b"content1")


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
# ^^^ see https://medium.com/@BartekSkwira/how-to-solve-pytest-pytestunraisableexceptionwarning-8d75a4d1f801
async def test_download_object(aws: S3Client) -> None:
    bucket = "bucket1"
    aws.create_bucket(Bucket=bucket)
    aws.put_object(Bucket=bucket, Key="test1", Body=b"content1")
    list_object_response = aws.list_objects_v2(Bucket=bucket, MaxKeys=1)
    if "Contents" not in list_object_response:
        raise ValueError("No objects in bucket")
    object_metadata = list_object_response["Contents"][0]

    s3 = _S3Client(aws, bucket)

    output_file = BytesIO()
    await s3.download_object(
        object_metadata.get("Key", ""),
        "test1",
        object_metadata.get("Size", 0),
        download_file=output_file,
        verify=False,
        show_progress=False,
    )
    assert output_file.getvalue() == b"content1"


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_download_object_verify(aws: S3Client) -> None:
    bucket = "bucket1"
    aws.create_bucket(Bucket=bucket)
    aws.put_object(Bucket=bucket, Key="test1", Body=b"content1", ChecksumAlgorithm="SHA1")
    list_object_response = aws.list_objects_v2(Bucket=bucket, MaxKeys=1)
    if "Contents" not in list_object_response:
        raise ValueError("No objects in bucket")
    object_metadata = list_object_response["Contents"][0]

    s3 = _S3Client(aws, bucket)

    output_file = BytesIO()
    await s3.download_object(
        object_metadata.get("Key", ""),
        "test1",
        object_metadata.get("Size", 0),
        download_file=output_file,
        verify=True,
        show_progress=False,
    )
    assert output_file.getvalue() == b"content1"


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@given(umbra_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_umbra_storage_client(aws: S3Client, tmp_path: Path, granules: UmbraStorageGranule) -> None:
    umbra = UmbraStorageClient(tmp_path)

    aws.create_bucket(Bucket=umbra._BUCKET)
    aws.put_object(
        Bucket=umbra._BUCKET,
        Key=f"sar-data/tasks/{granules.location}/{granules.granule_name}_GEC.tif",
        Body=b"content1",
        ACL="public-read",
    )
    aws.put_object(
        Bucket=umbra._BUCKET,
        Key=f"sar-data/tasks/{granules.location}/{granules.granule_name}_CPHD.cphd",
        Body=b"content2",
        ACL="public-read",
    )

    folder = await umbra.download(granules, show_progress=False)
    assert folder.exists()
    assert folder.parent.parent.parent == tmp_path / "Umbra"
    assert (folder / f"{granules.granule_name}_GEC.tif").read_bytes() == b"content1"
    assert (folder / f"{granules.granule_name}_CPHD.cphd").read_bytes() == b"content2"

    shutil.rmtree(folder)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@given(umbra_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_umbra_storage_client_products(aws: S3Client, tmp_path: Path, granules: UmbraStorageGranule) -> None:
    umbra = UmbraStorageClient(tmp_path)

    aws.create_bucket(Bucket=umbra._BUCKET)
    aws.put_object(
        Bucket=umbra._BUCKET,
        Key=f"sar-data/tasks/{granules.location}/{granules.granule_name}_GEC.tif",
        Body=b"content1",
        ACL="public-read",
    )
    aws.put_object(
        Bucket=umbra._BUCKET,
        Key=f"sar-data/tasks/{granules.location}/{granules.granule_name}_CPHD.cphd",
        Body=b"content2",
        ACL="public-read",
    )

    folder = await umbra.download(granules, show_progress=False, products=["GEC"])
    assert (folder / f"{granules.granule_name}_GEC.tif").read_bytes() == b"content1"
    assert not (folder / f"{granules.granule_name}_CPHD.cphd").exists()

    shutil.rmtree(folder)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@given(umbra_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_umbra_storage_client_no_cache(aws: S3Client, tmp_path: Path, granules: UmbraStorageGranule) -> None:
    umbra = UmbraStorageClient(cache_directory=None)

    aws.create_bucket(Bucket=umbra._BUCKET)
    aws.put_object(
        Bucket=umbra._BUCKET,
        Key=f"sar-data/tasks/{granules.location}/{granules.granule_name}_GEC.tif",
        Body=b"content1",
        ACL="public-read",
    )

    with pytest.raises(ValueError, match="No cache directory or output directory provided."):
        await umbra.download(granules)

    folder = await umbra.download(granules, output_dir=tmp_path, show_progress=False)
    assert (folder / f"{granules.granule_name}_GEC.tif").read_bytes() == b"content1"
    assert not (folder / f"{granules.granule_name}_CPHD.cphd").exists()

    shutil.rmtree(folder)


@pytest.mark.asyncio()
@given(s5p_granules())
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_copernicus_storage_client(aws: S3Client, tmp_path: Path, granules: CopernicusStorageGranule) -> None:
    copernicus = CopernicusStorageClient(access_key="testing", secret_access_key="testing", cache_directory=tmp_path)  # noqa: S106

    aws.create_bucket(Bucket=CopernicusStorageClient._BUCKET)
    aws.put_object(
        Bucket=copernicus._BUCKET,
        Key=f"{granules.location.removeprefix('/eodata/')}/{granules.granule_name}",
        Body=b"content1",
        ACL="public-read",
    )

    folder = await copernicus.download(granules, show_progress=False)
    assert folder.exists()
    assert (folder / granules.granule_name).read_bytes() == b"content1"

    shutil.rmtree(folder)
