import os
from collections.abc import Iterator
from pathlib import Path

import boto3
import pytest
from _pytest.fixtures import SubRequest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from tilebox.workflows.cache import AmazonS3Cache, InMemoryCache, JobCache, LocalFileSystemCache


@pytest.fixture
def _aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_SECURITY_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_SESSION_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def aws(_aws_credentials: None) -> Iterator[S3Client]:
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


caches = ["LocalFileSystem", "InMemory", "AmazonS3", "AmazonS3_no_prefix"]


@pytest.fixture
def cache(request: SubRequest, tmp_path: Path, aws: S3Client) -> JobCache:
    match request.param:
        case "LocalFileSystem":
            return LocalFileSystemCache(tmp_path)
        case "InMemory":
            return InMemoryCache()
        case "AmazonS3":
            bucket = "bucket1"
            aws.create_bucket(Bucket=bucket)
            return AmazonS3Cache(bucket, prefix="test")
        case "AmazonS3_no_prefix":
            bucket = "bucket1"
            aws.create_bucket(Bucket=bucket)
            return AmazonS3Cache(bucket, prefix="")
        case _:
            raise ValueError("Invalid cache type")


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_contains(cache: JobCache) -> None:
    assert "test" not in cache
    cache["test"] = b"some-value"
    assert "test" in cache


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_set_and_get(cache: JobCache) -> None:
    cache["test"] = b"some-value"

    assert cache["test"] == b"some-value"


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_get_file_not_found(cache: JobCache) -> None:
    with pytest.raises(KeyError):
        cache["test"]


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_get_folder_not_found(cache: JobCache) -> None:
    with pytest.raises(KeyError):
        cache["dir/a"]


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_get_wrong_type(cache: JobCache) -> None:
    cache.group("dir")["a"] = b"1"
    with pytest.raises(KeyError):
        cache["dir"]


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_get_wrong_type_nested(cache: JobCache) -> None:
    cache["dir"] = b"1"
    with pytest.raises(KeyError):
        cache["dir/a"]


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_iter(cache: JobCache) -> None:
    cache["test"] = b"some-value"
    cache["other"] = b"some-value"

    assert sorted(cache) == ["other", "test"]


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_iter_file_only(cache: JobCache) -> None:
    cache.group("some")["a"] = b"1"
    cache["b"] = b"2"
    cache["c"] = b"3"

    assert sorted(cache) == ["b", "c"]


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_iter_nested(cache: JobCache) -> None:
    cache["a"] = b"1"
    g = cache.group("some")
    g["b"] = b"2"
    g["c"] = b"3"

    assert sorted(g) == ["b", "c"]


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_iter_dir_does_not_exist(cache: JobCache) -> None:
    g = cache.group("dir")

    # __iter__ should not raise value error
    assert sorted(g) == []


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_iter_on_file(cache: JobCache) -> None:
    cache["file"] = b"1"
    g = cache.group("file")

    # __iter__ should not raise value error
    assert sorted(g) == []


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_groups(cache: JobCache) -> None:
    cache.group("some").group("nested").group("group")["test"] = b"some-value"

    assert cache.group("some")["nested/group/test"] == b"some-value"
    assert cache.group("some/nested/group")["test"] == b"some-value"
    assert cache["some/nested/group/test"] == b"some-value"


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_groups_2(cache: JobCache) -> None:
    cache.group("some/nested/group")["test"] = b"some-value"

    assert cache.group("some")["nested/group/test"] == b"some-value"
    assert cache.group("some/nested/group")["test"] == b"some-value"
    assert cache["some/nested/group/test"] == b"some-value"


@pytest.mark.parametrize("cache", caches, indirect=True)
def test_items(cache: JobCache) -> None:
    cache["a"] = b"b"
    cache["c"] = b"d"

    assert sorted(cache.items()) == [("a", b"b"), ("c", b"d")]
