import json

import pytest

from tilebox.workflows import ExecutionContext, Task, runner
from tilebox.workflows.cache import AmazonS3Cache, GoogleStorageCache, InMemoryCache, LocalFileSystemCache, NoCache


class DiscoveryTaskB(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context


class DiscoveryTaskA(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context


@pytest.fixture(autouse=True)
def reset_runner_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_REGISTERED_TASKS", {})


def test_runner_discovery_payload_is_runtime_command_compatible(capsys: pytest.CaptureFixture[str]) -> None:
    runner.register(DiscoveryTaskB)
    runner.register(DiscoveryTaskA)

    exit_code = runner.main(["--tilebox-discover"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["protocol"] == "tilebox.discovery.v1"
    assert payload["runtime_kind"] == "python_uv"
    assert payload["discovery_kind"] == "runtime_command"
    assert payload["warnings"] == []
    assert [task["name"] for task in payload["tasks"]] == ["DiscoveryTaskA", "DiscoveryTaskB"]


def test_runner_discovery_fails_without_registered_tasks(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = runner.main(["--tilebox-discover"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["code"] == "TBX-PUB-012"


def test_runner_register_rejects_duplicates() -> None:
    runner.register(DiscoveryTaskA)
    with pytest.raises(ValueError, match="Duplicate task identifier"):
        runner.register(DiscoveryTaskA)


def test_resolve_worker_cache_defaults_to_inmemory_when_auto_and_no_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TILEBOX_WORKER_CACHE", raising=False)
    assert isinstance(runner._resolve_worker_cache(), InMemoryCache)


def test_resolve_worker_cache_supports_s3_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "s3://aws-cache-bucket/pref")

    cache = runner._resolve_worker_cache()
    assert isinstance(cache, AmazonS3Cache)
    assert cache.bucket == "aws-cache-bucket"
    assert str(cache.prefix) == "pref"


def test_resolve_worker_cache_supports_gcs_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    bucket_name = "gcp-cache-bucket"
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", f"gcs://{bucket_name}/jobs")

    class _FakeStorageClient:
        def __init__(self, project: str | None) -> None:
            self.project = project

        def bucket(self, name: str) -> str:
            return f"bucket:{name}"

    monkeypatch.setattr(
        runner, "_google_storage_cache", lambda b, p: GoogleStorageCache(_FakeStorageClient(None).bucket(b), p)
    )

    cache = runner._resolve_worker_cache()
    assert isinstance(cache, GoogleStorageCache)
    assert cache.bucket == f"bucket:{bucket_name}"


def test_resolve_worker_cache_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "invalid")
    with pytest.raises(ValueError, match="Invalid TILEBOX_WORKER_CACHE"):
        runner._resolve_worker_cache()


def test_resolve_worker_cache_requires_bucket_for_remote_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "s3:///jobs")
    with pytest.raises(ValueError, match="must include a bucket"):
        runner._resolve_worker_cache()


def test_resolve_worker_cache_supports_none_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "none")
    assert isinstance(runner._resolve_worker_cache(), NoCache)


def test_resolve_worker_cache_supports_filesystem_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "filesystem")
    cache = runner._resolve_worker_cache()
    assert isinstance(cache, LocalFileSystemCache)
    assert cache.root.as_posix() == "cache"


def test_resolve_worker_cache_auto_detects_file_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "file:///opt/tilebox/cache")
    cache = runner._resolve_worker_cache()
    assert isinstance(cache, LocalFileSystemCache)
    assert cache.root.as_posix() == "/opt/tilebox/cache"


def test_resolve_worker_cache_parses_s3_uri_bucket_and_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "s3://my-cache/jobs/prefix")
    cache = runner._resolve_worker_cache()
    assert isinstance(cache, AmazonS3Cache)
    assert cache.bucket == "my-cache"
    assert str(cache.prefix) == "jobs/prefix"


def test_resolve_worker_cache_rejects_unsupported_uri_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "https://example.com/cache")
    with pytest.raises(ValueError, match="Use one of: inmemory, none, filesystem"):
        runner._resolve_worker_cache()


def test_resolve_worker_cache_auto_detects_gcs_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    bucket_name = "gcp-cache-bucket"
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", f"gs://{bucket_name}/jobs")

    class _FakeStorageClient:
        def __init__(self, project: str | None) -> None:
            self.project = project

        def bucket(self, name: str) -> str:
            return f"bucket:{name}"

    monkeypatch.setattr(
        runner, "_google_storage_cache", lambda b, p: GoogleStorageCache(_FakeStorageClient(None).bucket(b), p)
    )

    cache = runner._resolve_worker_cache()
    assert isinstance(cache, GoogleStorageCache)
    assert cache.bucket == f"bucket:{bucket_name}"
    assert str(cache.prefix) == "jobs"


def test_resolve_worker_cache_rejects_file_uri_with_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TILEBOX_WORKER_CACHE", "file://opt/tilebox/cache")
    with pytest.raises(ValueError, match="Use file:///absolute/path"):
        runner._resolve_worker_cache()
