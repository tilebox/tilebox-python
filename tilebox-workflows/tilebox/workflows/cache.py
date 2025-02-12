import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from google.cloud.exceptions import NotFound
from google.cloud.storage import Blob, Bucket


class JobCache(ABC):
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


class InMemoryCache(JobCache):
    def __init__(self) -> None:
        """A simple in-memory cache implementation.

        Useful for testing and development. Provides no persistence, and
        no way of sharing data between multiple task runners.
        """
        self.cache: dict[str, bytes | InMemoryCache] = {}

    def __contains__(self, key: str) -> bool:
        return key in self.cache

    def __setitem__(self, key: str, value: bytes) -> None:
        parent_group, key = self._resolve_slashes(key, create_missing=False)
        parent_group.cache[key] = value

    def __getitem__(self, key: str) -> bytes:
        parent_group, key = self._resolve_slashes(key, create_missing=False)
        item = parent_group.cache[key]
        if not isinstance(item, bytes):
            # item is a directory
            raise KeyError(f"{key} is not cached!")
        return item

    def __iter__(self) -> Iterator[str]:
        for k, v in self.cache.items():
            if isinstance(v, bytes):
                yield k

    def group(self, key: str) -> "InMemoryCache":
        parent_group, key = self._resolve_slashes(key, create_missing=True)
        try:
            group = parent_group.cache[key]
        except KeyError:
            group = InMemoryCache()
            parent_group.cache[key] = group

        if not isinstance(group, InMemoryCache):
            # if key is a file, we return an empty group
            return InMemoryCache()
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
                    sub_group = InMemoryCache()
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
        self.root = root if isinstance(root, Path) else Path(root)

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
            return iter(())

        yield from sorted([str(f.relative_to(self.root)) for f in self.root.iterdir() if f.is_file()])

    def group(self, key: str) -> "LocalFileSystemCache":
        return LocalFileSystemCache(self.root / key)


class GoogleStorageCache(JobCache):
    def __init__(self, bucket: Bucket, prefix: str = "jobs") -> None:
        """A cache implementation that stores data in Google Cloud Storage.

        Args:
            bucket: The Google Cloud Storage bucket to use for the cache.
            prefix: A path prefix to append to all objects stored in the cache. Defaults to "jobs".
        """
        self.bucket = bucket
        self.prefix = Path(prefix)  # we still use pathlib here, because it's easier to work with when joining paths

    def _blob(self, key: str) -> Blob:
        return self.bucket.blob(str(self.prefix / key))

    def __contains__(self, key: str) -> bool:
        # GCS library has some weird typing issues, so let's ignore them for now
        return self._blob(key).exists()  # type: ignore[arg-type]

    def __setitem__(self, key: str, value: bytes) -> None:
        # GCS library has some weird typing issues, so let's ignore them for now
        self._blob(key).upload_from_file(BytesIO(value))  # type: ignore[arg-type]

    def __getitem__(self, key: str) -> bytes:
        try:
            # GCS library has some weird typing issues, so let's ignore them for now
            return self._blob(key).download_as_bytes()  # type: ignore[arg-type]
        except NotFound:
            raise KeyError(f"{key} is not cached!") from None

    def __iter__(self) -> Iterator[str]:
        # we need to add the trailing slash, to avoid listing other blobs that start with the same prefix, e.g.
        # consider the following blobs:
        #   jobs/folder/some_file.txt
        #   jobs/folder2/other_file.txt
        # if we just list all blobs with prefix "jobs/folder", we would get both of them, but we only want the
        # ones in the folder, so we add the trailing slash to only get the blobs in the folder
        prefix = str(self.prefix) + "/"
        # by specifying the delimiter as "/", we can emulate a directory structure, and only get the blobs directly
        # in the "folder", and not the ones in subfolders

        # GCS library has some weird typing issues, so let's ignore them for now
        blobs = self.bucket.list_blobs(prefix=prefix, delimiter="/")  # type: ignore[arg-type]

        # make the names relative to the cache prefix (but including the key in the name)
        for blob in blobs:
            yield str(Path(blob.name).relative_to(self.prefix))

    def group(self, key: str) -> "GoogleStorageCache":
        return GoogleStorageCache(self.bucket, prefix=str(self.prefix / key))


class AmazonS3Cache(JobCache):
    def __init__(self, bucket: str, prefix: str = "jobs") -> None:
        """A cache implementation that stores data in Amazon S3.

        Args:
            bucket: The Amazon S3 bucket to use for the cache.
            prefix: A path prefix to append to all objects stored in the cache. Defaults to "jobs".
        """
        self.bucket = bucket
        self.prefix = Path(prefix)
        with warnings.catch_warnings():
            # https://github.com/boto/boto3/issues/3889
            warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*datetime.utcnow.*")
            self._s3 = boto3.client("s3")

    def __contains__(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self.bucket, Key=str(self.prefix / key))
        except ClientError as e:
            err = e.response.get("Error", {})
            if err.get("Code", "") == "404":
                return False
            raise  # not a 404, re-raise the exception
        else:
            return True

    def __setitem__(self, key: str, value: bytes) -> None:
        self._s3.upload_fileobj(BytesIO(value), self.bucket, str(self.prefix / key))

    def __getitem__(self, key: str) -> bytes:
        item = BytesIO()
        try:
            self._s3.download_fileobj(self.bucket, str(self.prefix / key), item)
        except ClientError as e:
            err = e.response.get("Error", {})
            if err.get("Code", "") == "404":
                raise KeyError(f"{key} is not cached!") from None
            raise  # not a 404, re-raise the exception
        else:
            return item.getvalue()

    def __iter__(self) -> Iterator[str]:
        paginator = self._s3.get_paginator("list_objects_v2")
        prefix = str(self.prefix) + "/" if self.prefix != Path() else ""
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
            for item in page.get("Contents", []):
                bucket = str(Path(item.get("Key", "")).relative_to(self.prefix))
                if "/" not in bucket:  # only yield files directly in the prefix
                    yield bucket

    def group(self, key: str) -> "AmazonS3Cache":
        return AmazonS3Cache(self.bucket, prefix=str(self.prefix / key))
