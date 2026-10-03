from datetime import timedelta
from pathlib import Path
from typing import assert_type
from unittest.mock import MagicMock, patch

import boto3
import pytest
from _pytest.fixtures import SubRequest
from obstore.exceptions import GenericError
from obstore.store import LocalStore, MemoryStore

from tilebox.workflows.cache import (
    AmazonS3Cache,
    AzureBlobCache,
    GoogleStorageCache,
    InMemoryCache,
    JobCache,
    LocalFileSystemCache,
    ObstoreCache,
)


@pytest.fixture
def _aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use test credentials without contacting AWS metadata services."""
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(autouse=True)
def _azure_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AZURE_STORAGE_ACCOUNT_KEY",
        "AZURE_STORAGE_ACCESS_KEY",
        "AZURE_STORAGE_MASTER_KEY",
        "AZURE_STORAGE_SAS_KEY",
        "AZURE_STORAGE_SAS_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


caches = [
    "LocalFileSystem",
    "InMemory",
    "AmazonS3",
    "AmazonS3_no_prefix",
    "AzureBlob",
    "AzureBlob_no_prefix",
    "ObstoreMemory",
    "ObstoreLocal",
    "GoogleStorage",
]


@pytest.fixture
def cache(request: SubRequest, tmp_path: Path, _aws_credentials: None) -> JobCache:  # noqa: PLR0911
    match request.param:
        case "LocalFileSystem":
            return LocalFileSystemCache(tmp_path)
        case "InMemory":
            return InMemoryCache()
        case "AmazonS3" | "AmazonS3_no_prefix":
            with patch("obstore.store.S3Store", return_value=MemoryStore()):
                return AmazonS3Cache(
                    "bucket1", prefix="test" if request.param == "AmazonS3" else "", region="us-east-1"
                )
        case "AzureBlob" | "AzureBlob_no_prefix":
            with (
                patch("azure.identity.DefaultAzureCredential"),
                patch("obstore.store.AzureStore", return_value=MemoryStore()),
            ):
                return AzureBlobCache("account", "container", prefix="test" if request.param == "AzureBlob" else "")
        case "ObstoreMemory":
            return ObstoreCache(MemoryStore())
        case "ObstoreLocal":
            return ObstoreCache(LocalStore(tmp_path))
        case "GoogleStorage":
            with (
                patch("google.auth.default", return_value=(MagicMock(), "project")),
                patch("obstore.store.GCSStore", return_value=MemoryStore()),
            ):
                return GoogleStorageCache("test-bucket")
        case _:
            raise ValueError("Invalid cache type")


def test_azure_cache_credentials_and_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    # Azure cache groups share one store and credential provider without listing sibling prefixes.
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "wrongaccount")
    store = MemoryStore()
    with (
        patch("obstore.auth.azure.AzureCredentialProvider") as provider,
        patch("obstore.store.AzureStore", return_value=store) as constructor,
    ):
        cache = AzureBlobCache("cacheaccount", "cache-container")
        first = cache.group("folder")
        first["one"] = b"first"
        cache.group("folder2")["two"] = b"second"
        assert list(first) == ["one"]
        assert first["one"] == b"first"
        assert isinstance(first, ObstoreCache)
        assert first.store is store
        assert store.get("jobs/folder/one").bytes() == b"first"
        constructor.assert_called_once_with(
            "cache-container", account_name="cacheaccount", credential_provider=provider.return_value
        )
        provider.assert_called_once_with()


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("AZURE_STORAGE_ACCOUNT_KEY", "dGVzdA=="),
        ("AZURE_STORAGE_ACCESS_KEY", "dGVzdA=="),
        ("AZURE_STORAGE_MASTER_KEY", "dGVzdA=="),
        ("AZURE_STORAGE_SAS_KEY", "sv=1&sig=test"),
        ("AZURE_STORAGE_SAS_TOKEN", "sv=1&sig=test"),
    ],
)
def test_azure_cache_explicit_credentials(variable: str, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Account keys and SAS tokens bypass Azure Identity when constructing the cache store.
    monkeypatch.setenv(variable, value)
    with (
        patch("azure.identity.DefaultAzureCredential") as credential,
        patch("obstore.store.AzureStore", return_value=MemoryStore()) as constructor,
    ):
        AzureBlobCache("cacheaccount", "cache-container")
        constructor.assert_called_once_with("cache-container", account_name="cacheaccount")
        credential.assert_not_called()


def test_s3_cache_credentials_and_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    # S3 caches use session credentials and the bucket region, sharing one store across groups.
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "environment-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "environment-secret")
    boto3.setup_default_session(
        aws_access_key_id="configured-key",
        aws_secret_access_key="configured-secret",  # noqa: S106
        region_name="eu-west-2",
    )
    store = MemoryStore()
    with patch("obstore.store.S3Store", return_value=store) as constructor:
        cache = AmazonS3Cache("cache-bucket", region="ap-southeast-2")
        first = cache.group("folder")
        first["one"] = b"first"
        cache.group("folder2")["two"] = b"second"
        assert list(first) == ["one"]
        assert first["one"] == b"first"
        assert isinstance(first, ObstoreCache)
        assert first.store is store
        assert store.get("jobs/folder/one").bytes() == b"first"
        assert constructor.call_count == 1
        assert constructor.call_args.args == ("cache-bucket",)
        provider = constructor.call_args.kwargs["credential_provider"]
        assert provider()["access_key_id"] == "configured-key"
        assert provider.config["region"] == "eu-west-2"
        assert constructor.call_args.kwargs["region"] == "ap-southeast-2"
        assert provider.ttl == timedelta(0)


def test_google_storage_credentials_and_groups() -> None:
    # GCS caches request write access and share credentials across groups without listing sibling prefixes.
    credentials = MagicMock()
    store = MemoryStore()
    with (
        patch("google.auth.default", return_value=(credentials, "project")) as default,
        patch("obstore.store.GCSStore", return_value=store) as constructor,
    ):
        cache = GoogleStorageCache("cache-bucket")
        first = cache.group("folder")
        assert_type(cache.bucket, str)
        assert_type(first.bucket, str)
        assert_type(first, GoogleStorageCache[str])
        first["one"] = b"first"
        cache.group("folder2")["two"] = b"second"
        assert list(first) == ["one"]
        assert first["one"] == b"first"
        assert isinstance(first, GoogleStorageCache)
        assert first.bucket == "cache-bucket"
        assert first.store is store
        assert store.get("jobs/folder/one").bytes() == b"first"
        default.assert_called_once_with(scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
        assert constructor.call_count == 1
        assert constructor.call_args.args == ("cache-bucket",)
        assert constructor.call_args.kwargs["credential_provider"].credentials is credentials


@pytest.mark.parametrize("cache", ["AmazonS3", "GoogleStorage", "AzureBlob"], indirect=True)
@pytest.mark.parametrize("error_type", [GenericError, PermissionError, TimeoutError, OSError])
def test_cloud_cache_backend_errors(cache: ObstoreCache, error_type: type[Exception]) -> None:
    # Cloud caches and their groups preserve backend errors during reads, membership checks, and deletion.
    error = error_type("backend unavailable")
    store = MagicMock()
    store.get.side_effect = error
    store.delete.side_effect = error
    cache.store = store
    for target in (cache, cache.group("nested")):
        for operation in (target.__getitem__, target.__contains__, target.__delitem__):
            with pytest.raises(error_type) as raised:
                operation("key")
            assert raised.value is error


def test_local_cache_generic_error_is_not_a_missing_path(tmp_path: Path) -> None:
    # Local backend errors propagate unless the requested path has a file where a directory is needed.
    error = GenericError("disk unavailable")
    store = MagicMock(spec=LocalStore)
    store.prefix = tmp_path
    store.get.side_effect = error
    with pytest.raises(GenericError) as raised:
        ObstoreCache(store)["missing/key"]
    assert raised.value is error


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
