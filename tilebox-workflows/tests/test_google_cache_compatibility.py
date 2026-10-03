from collections.abc import Iterator
from typing import assert_type
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from google.api_core.exceptions import Forbidden, NotFound, ServiceUnavailable
from google.auth.credentials import AnonymousCredentials
from google.cloud.storage import Blob, Bucket, Client
from google.oauth2.credentials import Credentials
from requests import Response

from tilebox.workflows.cache import GoogleStorageCache


@pytest.fixture(params=[False, True], ids=["authenticated", "anonymous"])
def google_bucket(request: pytest.FixtureRequest) -> Iterator[Bucket]:
    credentials = AnonymousCredentials() if request.param else Credentials(token="configured-token")  # noqa: S106
    client = Client(
        project="configured-project",
        credentials=credentials,
        _http=MagicMock(),
        client_options={"api_endpoint": "https://custom.example.test"},
    )
    with (
        patch("google.auth.default", side_effect=AssertionError("Bucket credentials must not be replaced by ADC")),
        patch("obstore.store.GCSStore", side_effect=AssertionError("Bucket configuration must stay with its client")),
    ):
        yield client.bucket("configured-bucket", user_project="billing-project")


def test_google_bucket_read_preserves_client(google_bucket: Bucket) -> None:
    # Bucket reads and nested groups retain credentials, custom transport, endpoint, and requester-pays billing.
    credentials = google_bucket.client._credentials
    transport = google_bucket.client._http
    response = Response()
    response.status_code = 200
    response._content = b"configured client content"
    response._content_consumed = True
    response.raw = MagicMock(headers={})
    response.headers["content-length"] = str(len(response.content))
    transport.request.return_value = response
    root = GoogleStorageCache(google_bucket)
    cache = root.group("folder").group("nested")
    assert_type(root.bucket, Bucket)
    assert_type(cache.bucket, Bucket)
    assert_type(cache, GoogleStorageCache[Bucket])
    assert isinstance(cache, GoogleStorageCache)
    assert cache.bucket is root.bucket is google_bucket
    assert cache["file.txt"] == b"configured client content"
    assert google_bucket.client._credentials is credentials
    # Newer Google clients may also fetch bucket metadata in a background thread.
    downloads = [call for call in transport.request.call_args_list if call.args and "/download/" in call.args[1]]
    assert len(downloads) == 1
    method, url = downloads[0].args
    assert method == "GET"
    parsed = urlsplit(url)
    assert parsed.netloc == "custom.example.test"
    assert parsed.path.endswith("/configured-bucket/o/jobs%2Ffolder%2Fnested%2Ffile.txt")
    assert parse_qs(parsed.query)["userProject"] == ["billing-project"]


@pytest.mark.parametrize("prefix", ["jobs", ""])
def test_google_bucket_operations(google_bucket: Bucket, prefix: str) -> None:
    # Bucket caches preserve writes, membership, deletion, and delimiter-based listing for each group.
    cache = GoogleStorageCache(google_bucket, prefix).group("folder")
    path = f"{prefix}/folder" if prefix else "folder"
    with (
        patch.object(Blob, "upload_from_file", autospec=True) as upload,
        patch.object(Blob, "exists", autospec=True, return_value=True) as exists,
        patch.object(Blob, "delete", autospec=True) as delete,
        patch.object(google_bucket, "list_blobs", return_value=[Blob(f"{path}/one", google_bucket)]) as listing,
    ):
        cache["one"] = b"saved value"
        blob, stream = upload.call_args.args
        assert blob.bucket is google_bucket
        assert blob.name == f"{path}/one"
        assert stream.getvalue() == b"saved value"
        assert "one" in cache
        assert exists.call_args.args[0].name == f"{path}/one"
        assert list(cache) == ["one"]
        listing.assert_called_once_with(prefix=f"{path}/", delimiter="/")
        del cache["one"]
        assert delete.call_args.args[0].name == f"{path}/one"


@pytest.mark.parametrize("error_type", [NotFound, Forbidden, ServiceUnavailable])
def test_google_bucket_read_errors(google_bucket: Bucket, error_type: type[Exception]) -> None:
    # Only missing objects become KeyError; configured-client permission and backend errors propagate unchanged.
    error = error_type("read failed")
    with patch.object(Blob, "download_as_bytes", side_effect=error):
        expected = KeyError if error_type is NotFound else error_type
        with pytest.raises(expected) as raised:
            GoogleStorageCache(google_bucket).group("nested")["file"]
        if error_type is not NotFound:
            assert raised.value is error
