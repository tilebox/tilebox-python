from pathlib import Path

from tilebox.storage.aio import ASFStorageClient as _ASFStorageClient
from tilebox.storage.aio import CopernicusStorageClient as _CopernicusStorageClient
from tilebox.storage.aio import UmbraStorageClient as _UmbraStorageClient


class ASFStorageClient(_ASFStorageClient):
    def __init__(self, user: str, password: str, cache_directory: Path = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the Alaska Satellite Facility.

        Args:
            user: The username to use for authentication.
            password: The password to use for authentication.
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        super().__init__(user, password, cache_directory)
        self._syncify()


class UmbraStorageClient(_UmbraStorageClient):
    def __init__(self, cache_directory: Path | None = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the Umbra Open Data Catalog.

        Args:
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        super().__init__(cache_directory)
        self._syncify()


class CopernicusStorageClient(_CopernicusStorageClient):
    def __init__(
        self,
        access_key: str | None = None,
        secret_access_key: str | None = None,
        cache_directory: Path | None = Path.home() / ".cache" / "tilebox",
    ) -> None:
        """A tilebox storage client that downloads data from the Copernicus EO data.

        Args:
            access_key: The S3 Copernicus access key. If not provided, the AWS_ACCESS_KEY_ID environment
                variable will be used.
            secret_access_key: The S3 Copernicus secret access key. If not provided, the AWS_SECRET_ACCESS_KEY
                environment variable will be used.
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        super().__init__(access_key, secret_access_key, cache_directory)
        self._syncify()
