import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch
from uuid import UUID

import boto3
import obstore
import pytest
from azure.core.credentials import AccessToken
from botocore.credentials import RefreshableCredentials
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from google.auth.exceptions import DefaultCredentialsError
from obstore.store import AzureStore, MemoryStore, S3Store

from tilebox.datasets.uuid import uuid_to_uuid_message
from tilebox.workflows.automations import StorageEventTask
from tilebox.workflows.cache import AmazonS3Cache
from tilebox.workflows.client import Client
from tilebox.workflows.data import (
    AWSS3StorageLocation,
    AzureBlobStorageLocation,
    RunnerContext,
    StorageLocation,
    StorageType,
    _default_azure_storage_client,
    _default_gcs_storage_client,
    _default_s3_storage_client,
)
from tilebox.workflows.observability.tracing import NoopWorkflowTracer
from tilebox.workflows.workflows.v1 import storage_location_pb2 as storage_pb

_ID = UUID("01a0fd71-8262-2fde-7283-43dab469c23f")
_ACCOUNT = "/subscriptions/test/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sourceaccount"


@pytest.fixture(autouse=True)
def isolated_storage_clients() -> Iterator[None]:
    clients = (_default_gcs_storage_client, _default_s3_storage_client, _default_azure_storage_client)
    for client in clients:
        client.cache_clear()
    yield
    for client in clients:
        client.cache_clear()


@pytest.mark.parametrize(("method", "store_class"), [("gcs_client", "GCSStore"), ("s3_client", "S3Store")])
def test_cloud_client_cache(method: str, store_class: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # GCS and S3 reuse a store for the same bucket and keep different buckets separate.
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    with (
        patch("google.auth.default", return_value=(MagicMock(), "project")),
        patch(f"obstore.store.{store_class}", side_effect=[MemoryStore(), MemoryStore()]) as constructor,
    ):
        client = getattr(RunnerContext(), method)
        if method == "s3_client":
            client = partial(client, region="us-east-1")
        first = client("first-bucket")
        assert client("first-bucket") is first
        assert client("other-bucket") is not first
        assert constructor.call_count == 2


def test_gcs_adc_project_lookup_is_not_repeated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Repeated reads reuse ADC credentials instead of launching gcloud to rediscover the project.
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path))
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "explicit-project")
    (tmp_path / "application_default_credentials.json").write_text(
        json.dumps(
            {"type": "authorized_user", "client_id": "test-client", "client_secret": "test", "refresh_token": "test"}
        )
    )
    store = MemoryStore()
    obstore.put(store, "first.txt", b"first")
    obstore.put(store, "second.txt", b"second")
    location = StorageLocation(_ID, "adc-bucket", StorageType.GCS)
    with (
        patch("subprocess.check_output", return_value=b"discovered-project\n") as command,
        patch("obstore.store.GCSStore", return_value=store) as constructor,
    ):
        assert location.read("first.txt") == b"first"
        assert location.read("second.txt") == b"second"
        command.assert_called_once()
        assert command.call_args.args[0] == ("gcloud", "config", "get", "project")
        constructor.assert_called_once()


def test_gcs_discovery_error_is_not_hidden_or_cached() -> None:
    # Credential discovery failures reach the caller and a later read can retry discovery.
    store = MemoryStore()
    obstore.put(store, "file.txt", b"retried")
    location = StorageLocation(_ID, "retry-bucket", StorageType.GCS)
    with (
        patch("google.auth.default", side_effect=[DefaultCredentialsError("missing credentials"), (MagicMock(), None)]),
        patch("obstore.store.GCSStore", return_value=store),
    ):
        with pytest.raises(DefaultCredentialsError, match="missing credentials"):
            location.read("file.txt")
        assert location.read("file.txt") == b"retried"


def _azure_message() -> storage_pb.StorageLocation:
    return storage_pb.StorageLocation(
        id=uuid_to_uuid_message(_ID),
        reference=storage_pb.StorageLocationReference(
            type=storage_pb.STORAGE_TYPE_AZURE_BLOB,
            azure_blob=storage_pb.AzureBlobReference(storage_account_resource_id=_ACCOUNT, container="sourcecontainer"),
        ),
    )


@pytest.mark.parametrize("storage_type", [StorageType.GCS, StorageType.AWS_S3, StorageType.LOCAL])
def test_mixed_storage_location_ordering(storage_type: StorageType) -> None:
    # Azure and other storage locations sort together by ID before their bucket or container names.
    plain = StorageLocation(UUID(int=1), "z", storage_type)
    azure = AzureBlobStorageLocation(UUID(int=2), "a", StorageType.AZURE_BLOB, storage_account_resource_id=_ACCOUNT)
    assert plain < azure
    assert azure > plain
    assert sorted([azure, plain]) == [plain, azure]


def test_azure_trigger_read() -> None:
    # Deserialized Azure tasks read from the account and container supplied by the runner context.
    location = StorageLocation.from_message(_azure_message())
    assert isinstance(location, AzureBlobStorageLocation)
    assert location.type == StorageType.AZURE_BLOB
    assert location.location == "sourcecontainer"
    assert location.storage_account_resource_id == _ACCOUNT
    assert StorageLocation.from_message(location.to_message()) == location

    store = MemoryStore()
    key = "nested/hello + %20 ü.txt"
    expected = "Hello Azure! ü\n".encode()
    obstore.put(store, key, expected)
    context = RunnerContext(storage_locations=[location])
    task = StorageEventTask().once(location, key)
    restored = StorageEventTask._deserialize(task._serialize(), context)
    assert isinstance(restored.trigger.storage, AzureBlobStorageLocation)
    assert restored.trigger.storage.storage_account_resource_id == _ACCOUNT
    assert restored.trigger.storage.runner_context is context
    with patch.object(context, "azure_client", return_value=store) as client:
        assert restored.trigger.storage.read(restored.trigger.location) == expected
        client.assert_called_once_with(_ACCOUNT, "sourcecontainer")


def test_azure_client_coordinates_override_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # The account from API metadata takes precedence over the account configured in the environment.
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "wrongaccount")
    store = RunnerContext().azure_client(_ACCOUNT, "explicit-container")
    assert store.config["account_name"] == "sourceaccount"
    assert store.config["container_name"] == "explicit-container"


def test_azure_client_cache_separates_accounts_and_containers() -> None:
    # Azure clients are reused only when both the account and container match.
    context = RunnerContext()
    first = context.azure_client(_ACCOUNT, "one")
    assert context.azure_client(_ACCOUNT, "one") is first
    assert context.azure_client(_ACCOUNT, "two") is not first
    other = context.azure_client(_ACCOUNT.replace("sourceaccount", "otheraccount"), "one")
    assert other is not first
    assert other.config["account_name"] == "otheraccount"


def test_azure_identity_credentials() -> None:
    # Azure Identity supplies a storage-scoped token and its expiry to obstore.
    with (
        patch("azure.identity.DefaultAzureCredential") as credential,
        patch("obstore.store.AzureStore", wraps=AzureStore) as constructor,
    ):
        credential.return_value.get_token.return_value = AccessToken("test-token", 2000000000)
        RunnerContext().azure_client(_ACCOUNT, "identity-test")
        provider = constructor.call_args.kwargs["credential_provider"]
        assert provider() == {"token": "test-token", "expires_at": datetime.fromtimestamp(2000000000, UTC)}
        credential.return_value.get_token.assert_called_once_with("https://storage.azure.com/.default", tenant_id=None)
        credential.assert_called_once_with()


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
def test_azure_explicit_credentials(variable: str, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Explicit keys and SAS tokens use native obstore authentication without constructing Azure Identity.
    monkeypatch.setenv(variable, value)
    with (
        patch("azure.identity.DefaultAzureCredential") as credential,
        patch("obstore.store.AzureStore", wraps=AzureStore) as constructor,
    ):
        container = variable.lower().replace("_", "-")
        RunnerContext().azure_client(_ACCOUNT, container)
        constructor.assert_called_once_with(container, account_name="sourceaccount")
        credential.assert_not_called()


def test_azure_read_requires_account_metadata() -> None:
    # Missing or malformed Azure account resource IDs raise a clear error before a cloud request.
    location = StorageLocation(_ID, "container-only", StorageType.AZURE_BLOB)
    with pytest.raises(ValueError, match="missing its storage account resource ID"):
        location.read("file.txt")
    with pytest.raises(ValueError, match="Invalid Azure storage account resource ID"):
        RunnerContext().azure_client("https://sourceaccount.blob.core.windows.net", "container")


def test_gcs_trigger_read() -> None:
    # GCS tasks read the referenced bucket using scoped google-auth credentials.
    bucket = "storage-automation-test-gcp-2aa460e"
    message = storage_pb.StorageLocation(
        id=uuid_to_uuid_message(_ID),
        reference=storage_pb.StorageLocationReference(
            type=storage_pb.STORAGE_TYPE_GCS,
            gcs_bucket=storage_pb.GCSBucketReference(project_id="test-project", bucket=bucket),
        ),
    )
    location = StorageLocation.from_message(message)
    context = RunnerContext(storage_locations=[location])
    key = "nested/hello + %20 ü.txt"
    expected = b"GCS blob contents\n"
    store = MemoryStore()
    obstore.put(store, key, expected)
    task = StorageEventTask().once(location, key)
    restored = StorageEventTask._deserialize(task._serialize(), context)
    credentials = MagicMock()
    with (
        patch("google.auth.default", return_value=(credentials, "test-project")) as default_credentials,
        patch("obstore.store.GCSStore", return_value=store) as constructor,
    ):
        assert restored.trigger.storage.read(restored.trigger.location) == expected
        default_credentials.assert_called_once_with(scopes=["https://www.googleapis.com/auth/devstorage.read_only"])
        assert restored.trigger.storage.read(restored.trigger.location) == expected
        constructor.assert_called_once()
        assert constructor.call_args.args == (bucket,)
        provider = constructor.call_args.kwargs["credential_provider"]
        assert provider.credentials is credentials
        credentials.token = "test-token"  # noqa: S105
        credentials.expiry = None
        assert provider()["token"] == "test-token"  # noqa: S105
        credentials.refresh.assert_called_once_with(provider.request)


def test_s3_read_preserves_aws_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # S3 reads use credentials from the selected AWS profile rather than the default profile.
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    credentials = tmp_path / "credentials"
    credentials.write_text(
        "[default]\naws_access_key_id = default-key\naws_secret_access_key = default-secret\n"
        "[automation]\naws_access_key_id = profile-key\naws_secret_access_key = profile-secret\n"
    )
    config = tmp_path / "config"
    config.write_text("[profile automation]\nregion = eu-west-2\n")
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_DEFAULT_PROFILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_PROFILE", "automation")
    store = MemoryStore()
    key = "nested/aws.txt"
    expected = b"S3 blob contents\n"
    obstore.put(store, key, expected)
    with patch("obstore.store.S3Store", return_value=store) as constructor:
        assert AWSS3StorageLocation(_ID, "aws-bucket", StorageType.AWS_S3, region="eu-west-2").read(key) == expected
        assert constructor.call_args.args == ("aws-bucket",)
        provider = constructor.call_args.kwargs["credential_provider"]
        assert provider()["access_key_id"] == "profile-key"


def test_s3_read_preserves_default_session(monkeypatch: pytest.MonkeyPatch) -> None:
    # S3 reads retain credentials and region configured with boto3.setup_default_session().
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "environment-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "environment-secret")
    boto3.setup_default_session(
        aws_access_key_id="configured-key",
        aws_secret_access_key="configured-secret",  # noqa: S106
        region_name="eu-west-2",
    )
    store = MemoryStore()
    obstore.put(store, "file.txt", b"configured session")
    with patch("obstore.store.S3Store", return_value=store) as constructor:
        assert (
            AWSS3StorageLocation(_ID, "aws-bucket", StorageType.AWS_S3, region="eu-west-2").read("file.txt")
            == b"configured session"
        )
        provider = constructor.call_args.kwargs["credential_provider"]
        assert provider()["access_key_id"] == "configured-key"
        assert provider.config["region"] == "eu-west-2"


def test_s3_reference_region_and_store_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    # The API bucket region survives task serialization and overrides the session region in cached stores.
    session = MagicMock(region_name="us-east-1")
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", session)
    message = storage_pb.StorageLocation(
        id=uuid_to_uuid_message(_ID),
        reference=storage_pb.StorageLocationReference(
            type=storage_pb.STORAGE_TYPE_AWS_S3,
            aws_s3_bucket=storage_pb.AWSS3BucketReference(bucket="source-bucket", region="eu-west-2"),
        ),
    )
    location = StorageLocation.from_message(message)
    assert isinstance(location, AWSS3StorageLocation)
    assert StorageLocation.from_message(location.to_message()) == location
    context = RunnerContext(storage_locations=[location])
    task = StorageEventTask().once(location, "file.txt")
    restored = StorageEventTask._deserialize(task._serialize(), context)
    store = context.s3_client("source-bucket", region="eu-west-2")
    assert store.config["region"] == "eu-west-2"
    assert context.s3_client("source-bucket", region="eu-west-2") is store
    assert context.s3_client("source-bucket", region="ap-southeast-2") is not store
    session.client.assert_not_called()
    memory = MemoryStore()
    obstore.put(memory, "file.txt", b"regional object")
    with patch.object(context, "s3_client", return_value=memory) as client:
        assert restored.trigger.storage.read(restored.trigger.location) == b"regional object"
        client.assert_called_once_with("source-bucket", region="eu-west-2")


@pytest.mark.parametrize("forbidden", [False, True])
@pytest.mark.parametrize("cache", [False, True])
def test_s3_region_discovery(forbidden: bool, cache: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    # Bucket-only stores discover the region once, including when HeadBucket denies listing permission.
    client = boto3.Session(
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",  # noqa: S106
        region_name="us-east-1",
    ).client("s3")
    session = MagicMock(region_name=None)
    session.client.return_value = client
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", session)
    metadata = {"HTTPHeaders": {"x-amz-bucket-region": "eu-west-2"}}
    with Stubber(client) as stub:
        if forbidden:
            stub.add_client_error(
                "head_bucket",
                "403",
                http_status_code=403,
                response_meta=metadata,
                expected_params={"Bucket": "source-bucket"},
            )
        else:
            stub.add_response("head_bucket", {"ResponseMetadata": metadata}, {"Bucket": "source-bucket"})
        if cache:
            root = AmazonS3Cache("source-bucket")
            store = root.store
            assert root.group("nested").store is store
        else:
            store = RunnerContext().s3_client("source-bucket")
            assert RunnerContext().s3_client("source-bucket") is store
        stub.assert_no_pending_responses()
    assert store.config["region"] == "eu-west-2"
    session.client.assert_called_once_with("s3")


def test_s3_region_discovery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Discovery errors without a bucket-region header propagate instead of using the session region.
    session = MagicMock(region_name="us-east-1")
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", session)
    error = ClientError({"Error": {"Code": "AccessDenied"}}, "HeadBucket")
    session.client.return_value.head_bucket.side_effect = error
    with pytest.raises(ClientError) as raised:
        RunnerContext().s3_client("source-bucket")
    assert raised.value is error


@pytest.mark.parametrize("cache", [False, True])
def test_s3_temporary_credentials_refresh(cache: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    # Real signed requests use refreshed credentials after a short session expires, without recreating the store.
    now = datetime.now(UTC)
    refresh = MagicMock(
        return_value={
            "access_key": "refreshed-key",
            "secret_key": "secret",
            "token": "new-token",
            "expiry_time": (now + timedelta(hours=1)).isoformat(),
        }
    )
    credentials = RefreshableCredentials(
        "initial-key",
        "secret",
        "initial-token",
        now + timedelta(minutes=16),
        refresh_using=refresh,
        method="test",
        time_fetcher=lambda: now,
    )
    session = MagicMock(region_name="us-east-1")
    session.get_credentials.return_value = credentials
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", session)
    authorizations: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            authorizations.append(self.headers["Authorization"])
            self.send_response(200)
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"data")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            constructor = partial(S3Store, endpoint=f"http://127.0.0.1:{server.server_port}", allow_http=True)
            with patch("obstore.store.S3Store", side_effect=constructor):
                store = (
                    AmazonS3Cache("bucket", region="eu-west-2").store
                    if cache
                    else RunnerContext().s3_client("bucket", "eu-west-2")
                )
            assert obstore.get(store, "key").bytes() == b"data"
            refresh.assert_not_called()
            now += timedelta(minutes=17)
            assert obstore.get(store, "key").bytes() == b"data"
            refresh.assert_called_once()
        finally:
            server.shutdown()
            thread.join()
    assert len(authorizations) == 2
    assert "Credential=initial-key/" in authorizations[0]
    assert "Credential=refreshed-key/" in authorizations[1]
    assert all("/eu-west-2/s3/" in authorization for authorization in authorizations)


def test_local_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    working_directory = tmp_path / "work"
    working_directory.mkdir()
    monkeypatch.chdir(working_directory)
    key = "nested/hello + %20 ü.txt"
    expected = b"existing provider content"
    storage = StorageLocation.from_message(
        storage_pb.StorageLocation(
            id=uuid_to_uuid_message(_ID),
            reference=storage_pb.StorageLocationReference(
                type=storage_pb.STORAGE_TYPE_LOCAL,
                local=storage_pb.LocalReference(path=str(tmp_path)),
            ),
        )
    )
    (tmp_path / "nested").mkdir()
    (tmp_path / key).write_bytes(expected)
    context = RunnerContext(storage_locations=[storage])
    task = StorageEventTask().once(storage, key)
    restored = StorageEventTask._deserialize(task._serialize(), context)
    assert restored.trigger.storage.read(restored.trigger.location) == expected
    with pytest.raises(FileNotFoundError):
        storage.read("missing.txt")


@pytest.mark.parametrize("root_kind", ["empty_path", "missing", "file"])
def test_local_read_requires_available_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root_kind: str) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "file.txt").write_bytes(b"must not fall back to the current directory")
    root = tmp_path / "root"
    if root_kind == "file":
        root.write_bytes(b"not a directory")
    storage = StorageLocation(_ID, "" if root_kind == "empty_path" else str(root), StorageType.LOCAL)
    with pytest.raises(ValueError, match="Local storage location root is not available"):
        storage.read("file.txt")
    if root_kind == "missing":
        assert not root.exists()


def test_local_read_accepts_empty_directory(tmp_path: Path) -> None:
    storage = StorageLocation(_ID, str(tmp_path), StorageType.LOCAL)
    with pytest.raises(FileNotFoundError):
        storage.read("missing.txt")


@pytest.mark.parametrize(
    ("reference", "expected_type", "expected_location"),
    [
        (
            storage_pb.StorageLocationReference(
                type=storage_pb.STORAGE_TYPE_GCS,
                gcs_bucket=storage_pb.GCSBucketReference(project_id="project", bucket="bucket"),
            ),
            StorageType.GCS,
            "bucket",
        ),
        (
            storage_pb.StorageLocationReference(
                type=storage_pb.STORAGE_TYPE_AWS_S3,
                aws_s3_bucket=storage_pb.AWSS3BucketReference(bucket="bucket"),
            ),
            StorageType.AWS_S3,
            "bucket",
        ),
        (
            storage_pb.StorageLocationReference(
                type=storage_pb.STORAGE_TYPE_LOCAL, local=storage_pb.LocalReference(path="/data")
            ),
            StorageType.LOCAL,
            "/data",
        ),
    ],
)
def test_reference_coordinates(
    reference: storage_pb.StorageLocationReference, expected_type: StorageType, expected_location: str
) -> None:
    # Structured GCS, S3, and filesystem references map to the expected storage type and location.
    storage = StorageLocation.from_message(
        storage_pb.StorageLocation(id=uuid_to_uuid_message(_ID), reference=reference)
    )
    assert storage.type == expected_type
    assert storage.location == expected_location


def test_grpc_storage_location_service_route() -> None:
    # gRPC listing uses StorageLocationService and retains Azure account metadata.
    channel = MagicMock()
    channel.unary_unary.return_value.return_value = storage_pb.StorageLocations(locations=[_azure_message()])
    with (
        patch("tilebox.workflows.client.open_channel", return_value=channel),
        patch("tilebox.workflows.client.WorkflowTracer", return_value=NoopWorkflowTracer()),
    ):
        locations = Client(token="test-key").storage_locations().all()  # noqa: S106
    assert isinstance(locations[0], AzureBlobStorageLocation)
    assert locations[0].storage_account_resource_id == _ACCOUNT
    assert "/workflows.v1.StorageLocationService/ListStorageLocations" in [
        call.args[0] for call in channel.unary_unary.call_args_list
    ]


def test_http1_storage_location_service_route() -> None:
    # HTTP/1.1 listing uses the Connect storage-location client and retains Azure account metadata.
    with (
        patch(
            "tilebox.workflows.workflows.v1.storage_location_connect.StorageLocationServiceClientSync.list_storage_locations",
            return_value=storage_pb.StorageLocations(locations=[_azure_message()]),
        ) as list_locations,
        patch("tilebox.workflows.client.WorkflowTracer", return_value=NoopWorkflowTracer()),
    ):
        locations = Client(token="test-key", transport="http1").storage_locations().all()  # noqa: S106
    assert isinstance(locations[0], AzureBlobStorageLocation)
    assert locations[0].storage_account_resource_id == _ACCOUNT
    list_locations.assert_called_once()
