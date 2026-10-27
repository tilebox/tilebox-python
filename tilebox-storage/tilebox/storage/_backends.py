"""Built-in namespace parsers and obstore factories."""

import re
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import SplitResult, unquote, urlsplit, urlunsplit

from tilebox.storage._registry import Registry, StoreSpec

if TYPE_CHECKING:
    from obstore.store import ObjectStore

    from tilebox.datasets.stac.v1.storage_pb import StorageScheme


def register_backends(registry: Registry) -> None:
    unspecified = (None, "unspecified")
    registry.register_backend(
        "file", uri_schemes=("file",), storage_types=unspecified, parse=_file, create=_local_store
    )
    registry.register_backend(
        "s3",
        uri_schemes=("s3",),
        storage_types=(*unspecified, "aws_s3", "custom_s3"),
        parse=_s3,
        create=partial(_cloud_store, "S3Store"),
    )
    registry.register_backend(
        "gcs",
        uri_schemes=("gs", "gcs"),
        storage_types=(*unspecified, "google_cloud_storage"),
        parse=_gcs,
        create=partial(_cloud_store, "GCSStore"),
    )
    azure_factory = partial(_cloud_store, "AzureStore")
    registry.register_backend(
        "azure",
        uri_schemes=("az", "azure", "abfs", "abfss"),
        storage_types=(*unspecified, "microsoft_azure"),
        parse=_azure,
        create=azure_factory,
    )
    registry.register_backend(
        "azure",
        uri_schemes=("https",),
        storage_types=("microsoft_azure",),
        parse=_azure,
        create=azure_factory,
    )
    registry.register_backend(
        "http",
        uri_schemes=("http", "https"),
        storage_types=(*unspecified, "aws_s3", "custom_s3", "google_cloud_storage"),
        parse=_http,
        create=_http_store,
    )


def _unsigned_uri(href: str) -> SplitResult:
    parsed = urlsplit(href)
    if not parsed.netloc or parsed.query or parsed.fragment or parsed.password:
        raise ValueError("expected an unsigned storage URI without query, fragment, or password")
    return parsed


def _file(href: str, _storage: "StorageScheme | None") -> tuple[StoreSpec, str]:
    parsed = urlsplit(href)
    if parsed.scheme and (parsed.netloc not in {"", "localhost"} or parsed.query or parsed.fragment):
        raise ValueError("expected a local file URI without query or fragment")
    path = Path(unquote(parsed.path) if parsed.scheme else href).absolute()
    return StoreSpec("file", path.anchor), str(path.relative_to(path.anchor))


def _s3(href: str, storage: "StorageScheme | None") -> tuple[StoreSpec, str]:
    parsed = _unsigned_uri(href)
    if parsed.username:
        raise ValueError("S3 URI must not contain credentials")
    options: dict[str, str | bool] = {}
    if storage is not None:
        if storage.has_field("region"):
            options["region"] = storage.region
        if storage.has_field("requester_pays"):
            options["request_payer"] = storage.requester_pays
        if storage.known_type.name == "CUSTOM_S3":
            endpoint = urlsplit(storage.platform)
            if (
                endpoint.scheme != "https"
                or not endpoint.netloc
                or endpoint.username
                or endpoint.query
                or endpoint.fragment
            ):
                raise ValueError("custom S3 storage requires an HTTPS endpoint without credentials")
            options["aws_endpoint_url_s3"] = storage.platform
    return StoreSpec("s3", parsed.netloc, tuple(sorted(options.items()))), unquote(parsed.path.lstrip("/"))


def _gcs(href: str, _storage: "StorageScheme | None") -> tuple[StoreSpec, str]:
    parsed = _unsigned_uri(href)
    if parsed.username:
        raise ValueError("GCS URI must not contain credentials")
    return StoreSpec("gcs", parsed.netloc), unquote(parsed.path.lstrip("/"))


def _azure(href: str, storage: "StorageScheme | None") -> tuple[StoreSpec, str]:
    parsed = _unsigned_uri(href)
    account = storage.account if storage is not None else ""
    if parsed.scheme in {"abfs", "abfss"}:
        container = parsed.username or parsed.netloc
        if parsed.username:
            account = (parsed.hostname or "").removesuffix(".dfs.core.windows.net")
            if parsed.netloc != f"{container}@{account}.dfs.core.windows.net":
                raise ValueError("unsupported Azure DFS authority")
        path = parsed.path.lstrip("/")
    else:
        if parsed.scheme == "https":
            account = parsed.netloc.removesuffix(".blob.core.windows.net")
            if parsed.netloc != f"{account}.blob.core.windows.net":
                raise ValueError("expected an unsigned Azure href matching the account and container")
        else:
            account = parsed.netloc
        container, _, path = parsed.path.lstrip("/").partition("/")
    if not re.fullmatch(r"[a-z0-9]{3,24}", account) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", container):
        raise ValueError("Azure storage requires a valid account and container")
    origin = f"https://{account}.blob.core.windows.net"
    if storage is not None:
        declared_container = storage.additional_properties.get("container")
        if (
            (storage.account and storage.account != account)
            or (declared_container is not None and declared_container.to_python() != container)
            or (storage.platform and storage.platform not in {origin, "https://{account}.blob.core.windows.net"})
        ):
            raise ValueError("expected an unsigned Azure href matching the account and container")
    options = (("account_name", account), ("endpoint", origin), ("use_emulator", False))
    return StoreSpec("azure", container, options), unquote(path)


def _http(href: str, _storage: "StorageScheme | None") -> tuple[StoreSpec, str]:
    parsed = urlsplit(href)
    if not parsed.netloc or parsed.username or parsed.fragment:
        raise ValueError("HTTP locations require a host and no userinfo or fragment")
    # Queries stay on the base URL. Obstore appends and escapes only object path segments.
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", parsed.query, ""))
    return StoreSpec("http", origin), unquote(parsed.path.lstrip("/"))


def _cloud_store(class_name: str, spec: StoreSpec) -> "ObjectStore":
    from obstore import store  # noqa: PLC0415

    options: dict[str, Any] = dict(spec.options)
    options["skip_signature"] = spec.credential_provider is None
    if spec.credential_provider is not None:
        options["credential_provider"] = spec.credential_provider
    return getattr(store, class_name)(spec.root, **options)


def _local_store(spec: StoreSpec) -> "ObjectStore":
    from obstore.store import LocalStore  # noqa: PLC0415

    return LocalStore(spec.root)


def _http_store(spec: StoreSpec) -> "ObjectStore":
    from obstore.store import HTTPStore  # noqa: PLC0415

    return HTTPStore(spec.root, client_options={"allow_http": spec.root.startswith("http://")})
