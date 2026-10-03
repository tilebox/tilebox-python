import contextlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from pathlib import PurePosixPath as ObjectPath
from threading import RLock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from obstore.store import ObjectStore
else:
    ObjectStore = Any


class JobCache(ABC):
    """Cache shared by tasks belonging to the same job.

    Task executions may access a cache concurrently, including from different threads in a shared worker runtime.
    Implementations must therefore make individual cache operations and :meth:`group` thread-safe. Sequences of
    operations, such as checking for a key before setting it, are not atomic.
    """

    @abstractmethod
    def __contains__(self, key: str) -> bool: ...
    @abstractmethod
    def __setitem__(self, key: str, value: bytes) -> None: ...
    @abstractmethod
    def __getitem__(self, key: str) -> bytes: ...
    @abstractmethod
    def __iter__(self) -> Iterator[str]: ...
    @abstractmethod
    def group(self, key: str) -> "JobCache": ...

    def items(self) -> Iterator[tuple[str, bytes]]:
        for key in self:
            yield key, self[key]


class NoCacheError(ValueError):
    pass


class NoCache(JobCache):
    """A no-op cache that will raise an error if it's used."""

    def __contains__(self, key: str) -> bool:
        raise NoCacheError(
            f"{key} is not cached: "
            f"No cache configured! Specify a cache using the cache argument when instantiating the task runner."
        )

    def __setitem__(self, key: str, value: bytes) -> None:
        raise NoCacheError(
            f"Cannot save {key} with value of {len(value)} bytes: "
            f"No cache configured! Specify a cache using the cache argument when instantiating the task runner. "
        )

    def __getitem__(self, key: str) -> bytes:
        raise NoCacheError(
            f"{key} is not cached: "
            f"No cache configured! Specify a cache using the cache argument when instantiating the task runner."
        )

    def __iter__(self) -> Iterator[str]:
        raise NoCacheError(
            "No cache configured! Specify a cache using the cache argument when instantiating the task runner."
        )

    def group(self, key: str) -> "NoCache":
        _ = key
        return self


class ObstoreCache(JobCache):
    def __init__(self, store: ObjectStore, prefix: str | ObjectPath = ObjectPath(".")) -> None:
        """A cache implementation backed by an obstore ObjectStore.

        This cache implementation is the recommended way of working with the cache, as it provides a unified interface
        for working with different object stores, while also providing a way to transparently work with local files
        as well.

        Args:
            store: The object store to use for the cache.
            prefix: A path prefix to append to all objects stored in the cache. Defaults to no prefix.
        """
        self.store = store
        self.prefix = ObjectPath(prefix)

    def __contains__(self, key: str) -> bool:
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):
            self.store.get(str(self.prefix / key))
            return True  # if get is successful, we know the key is in the cache

        return False

    def __setitem__(self, key: str, value: bytes) -> None:
        self.store.put(str(self.prefix / key), value)

    def __delitem__(self, key: str) -> None:
        try:
            self.store.delete(str(self.prefix / key))
        except (FileNotFoundError, NotADirectoryError):
            raise KeyError(f"{key} is not cached!") from None

    def __getitem__(self, key: str) -> bytes:
        from obstore.exceptions import GenericError  # noqa: PLC0415
        from obstore.store import LocalStore  # noqa: PLC0415

        try:
            entry = self.store.get(str(self.prefix / key))
            return bytes(entry.bytes())
        except (FileNotFoundError, NotADirectoryError):
            raise KeyError(f"{key} is not cached!") from None
        except GenericError:
            # LocalStore wraps a file used as a parent directory in GenericError.
            if isinstance(self.store, LocalStore) and self.store.prefix is not None:
                try:
                    (self.store.prefix / self.prefix / key).stat()
                except NotADirectoryError:
                    raise KeyError(f"{key} is not cached!") from None
                except OSError:
                    pass
            raise

    def __iter__(self) -> Iterator[str]:
        prefix = "" if self.prefix == ObjectPath(".") else str(self.prefix)
        for obj in self.store.list_with_delimiter(prefix)["objects"]:
            path: str = obj["path"]
            yield path.removeprefix(str(self.prefix) + "/")

    def group(self, key: str) -> "ObstoreCache":
        return ObstoreCache(self.store, prefix=str(self.prefix / key))


class InMemoryCache(JobCache):
    def __init__(self, *, _lock: Any | None = None) -> None:
        """A simple in-memory cache implementation.

        Useful for testing and development. Provides no persistence, and
        no way of sharing data between multiple task runners.
        """
        self.cache: dict[str, bytes | InMemoryCache] = {}
        self._lock = _lock or RLock()

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self.cache

    def __setitem__(self, key: str, value: bytes) -> None:
        with self._lock:
            parent_group, key = self._resolve_slashes(key, create_missing=False)
            parent_group.cache[key] = value

    def __getitem__(self, key: str) -> bytes:
        with self._lock:
            parent_group, key = self._resolve_slashes(key, create_missing=False)
            item = parent_group.cache[key]
            if not isinstance(item, bytes):
                # item is a directory
                raise KeyError(f"{key} is not cached!")
            return item

    def __iter__(self) -> Iterator[str]:
        with self._lock:
            return iter([key for key, value in self.cache.items() if isinstance(value, bytes)])

    def group(self, key: str) -> "InMemoryCache":
        with self._lock:
            parent_group, key = self._resolve_slashes(key, create_missing=True)
            try:
                group = parent_group.cache[key]
            except KeyError:
                group = InMemoryCache(_lock=self._lock)
                parent_group.cache[key] = group

            if not isinstance(group, InMemoryCache):
                # if key is a file, we return an empty group
                return InMemoryCache(_lock=self._lock)
            return group

    def _resolve_slashes(self, key: str, create_missing: bool = False) -> tuple["InMemoryCache", str]:
        """Resolve slashes in a given cache key, by converting them into nested groups.

        For example if the key is "a/b/c", the parent group is "a" -> "b", and the key is "c".

        Args:
            key: The key to get the parent group for.
            create_missing: If True, recursively create missing parent groups if they don't exist.

        Returns:
            The parent group and the key, where the key is the last part of the input key (after the last "/").
        """

        # we emulate a hierarchical structure by using the "/" character as a separator
        # e.g. .group("a/b") should behave exactly like .group("a").group("b")
        parts = key.split("/")

        group = self

        for part in parts[:-1]:  # all but the last part must be groups
            try:
                sub_group = group.cache[part]
            except KeyError:
                if create_missing:
                    # create a new group for this key if it doesn't exist
                    sub_group = InMemoryCache(_lock=self._lock)
                    group.cache[part] = sub_group
                else:
                    raise KeyError(f"{part} is not cached!") from None

            if isinstance(sub_group, InMemoryCache):
                group = sub_group
            else:
                # if the key is a file, we can't go any deeper
                raise KeyError(f"{part} is not cached!") from None

        return group, parts[-1]


class LocalFileSystemCache(JobCache):
    def __init__(self, root: Path | str = Path("cache")) -> None:
        """A cache implementation that stores data on the local file system.

        Useful for testing and development. Provides a quick way of testing workflows execution in parallel
        with multiple task runners, but requires all task runners to have access to the same file system.

        Args:
            root: File system path where the cache will be stored. Defaults to "cache" in the current working directory.
        """
        self.root = Path(root)

    def __contains__(self, key: str) -> bool:
        return (self.root / key).exists()

    def __setitem__(self, key: str, value: bytes) -> None:
        file = self.root / key
        file.parent.mkdir(exist_ok=True, parents=True)
        with file.open("wb") as f:
            f.write(value)

    def __getitem__(self, key: str) -> bytes:
        file = self.root / key
        if not file.is_file():
            raise KeyError(f"{key} is not cached!")

        with file.open("rb") as f:
            return f.read()

    def __iter__(self) -> Iterator[str]:
        if not self.root.is_dir():
            # if the root directory doesn't exist or is not a directory, return an empty iterator
            return

        yield from sorted([str(f.relative_to(self.root)) for f in self.root.iterdir() if f.is_file()])

    def group(self, key: str) -> "LocalFileSystemCache":
        return LocalFileSystemCache(self.root / key)


class GoogleStorageCache(ObstoreCache):
    def __init__(self, bucket: str, prefix: str | ObjectPath = "jobs") -> None:
        """A cache implementation that stores data in Google Cloud Storage.

        Args:
            bucket: The Google Cloud Storage bucket name. Credentials come from Google Auth.
            prefix: A path prefix to append to all objects stored in the cache. Defaults to "jobs".
        """
        import google.auth  # noqa: PLC0415
        from obstore.auth.google import GoogleCredentialProvider  # noqa: PLC0415
        from obstore.store import GCSStore  # noqa: PLC0415

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
        store = GCSStore(bucket, credential_provider=GoogleCredentialProvider(credentials=credentials))
        super().__init__(store, prefix)


class AmazonS3Cache(ObstoreCache):
    def __init__(self, bucket: str, prefix: str | ObjectPath = "jobs", *, region: str | None = None) -> None:
        """A cache implementation that stores data in Amazon S3.

        Args:
            bucket: The Amazon S3 bucket name. Credentials come from the boto3 session.
            prefix: A path prefix to append to all objects stored in the cache. Defaults to "jobs".
            region: The bucket region. If omitted, discover it with HeadBucket.
        """
        from tilebox.workflows.data import _s3_storage_client  # noqa: PLC0415

        super().__init__(_s3_storage_client(bucket, region), prefix)


class AzureBlobCache(ObstoreCache):
    def __init__(self, account_name: str, container: str, prefix: str | ObjectPath = "jobs") -> None:
        """Store cached data in Azure Blob Storage.

        Args:
            account_name: The storage account name. Credentials come from Azure Identity,
                or an account key or SAS token configured in the environment.
            container: The Azure Blob Storage container name.
            prefix: A path prefix for cached objects. Defaults to "jobs".
        """
        from tilebox.workflows.data import _azure_storage_client  # noqa: PLC0415

        super().__init__(_azure_storage_client(account_name, container), prefix)
