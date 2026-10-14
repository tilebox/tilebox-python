"""Internal, per-client dispatch for asset storage and authentication.

Plugins resolve metadata without I/O. Store construction and credential fetching
are separate: the client caches stores, and obstore refreshes their credentials.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from obstore.store import ObjectStore, S3CredentialProvider

    from tilebox.datasets.assets.assets import AssetLocation
    from tilebox.datasets.datasets.stac.v1.authentication_pb import AuthenticationScheme, SignedURLFlow
    from tilebox.datasets.datasets.stac.v1.storage_pb import StorageScheme


@dataclass(frozen=True, slots=True)
class StoreSpec:
    """Store construction inputs, also used as the client's cache key.

    ``root`` is a bucket, container, filesystem root, or HTTP base URL. Options
    must be immutable and sorted. Credential providers must be hashable: equality
    means the same credential identity and scope, never the current token value.
    Object keys and dataset prefixes belong outside this spec.
    """

    backend: str
    root: str = field(repr=False)
    options: tuple[tuple[str, str | bool], ...] = ()
    credential_provider: Callable[[], Any] | None = field(default=None, repr=False)


BackendParser = Callable[[str, "StorageScheme | None"], tuple[StoreSpec, str]]
StoreFactory = Callable[[StoreSpec], "ObjectStore"]
AuthenticationResolver = Callable[[StoreSpec, str, str, "AuthenticationScheme | None"], tuple[StoreSpec, str]]
SigningResolver = Callable[[StoreSpec, str, "SignedURLFlow"], tuple[StoreSpec, str]]


class Registry:
    """An explicit set of supported backends, authentication types, and signers.

    Each client owns its built-in registrations. This is an implementation detail,
    not a public plugin API. No plugins are discovered from catalog metadata.
    """

    def __init__(self) -> None:
        self._backends: dict[tuple[str, str | None], BackendParser] = {}
        self._factories: dict[str, StoreFactory] = {}
        self._authentication: dict[tuple[str, str | None], AuthenticationResolver] = {}
        self._signers: dict[tuple[str, str], SigningResolver] = {}

    @classmethod
    def default(cls, *, s3_credentials: Mapping[str, "S3CredentialProvider"] | None = None) -> "Registry":
        """Create built-ins, optionally binding S3 auth scheme names to providers.

        Providers are invoked on reads, not during resolution. Environment or
        profile discovery must be implemented by an explicitly supplied provider.
        """
        from tilebox.storage._authentication import register_authentication  # noqa: PLC0415
        from tilebox.storage._backends import register_backends  # noqa: PLC0415

        registry = cls()
        register_backends(registry)
        register_authentication(registry, s3_credentials or {})
        return registry

    def register_backend(
        self,
        name: str,
        *,
        uri_schemes: tuple[str, ...],
        storage_types: tuple[str | None, ...],
        parse: BackendParser,
        create: StoreFactory,
    ) -> None:
        """Register one backend's supported URI/storage combinations and factory.

        Parsers validate metadata and return a spec with ``backend=name`` plus a
        decoded key or prefix. Raise ValueError with a credential-free explanation
        for unsupported metadata. Neither parsing nor construction may fetch data.
        """
        keys = [(uri, storage) for uri in uri_schemes for storage in storage_types]
        if (name in self._factories and self._factories[name] != create) or any(key in self._backends for key in keys):
            raise ValueError("backend registration overlaps an existing registration")
        self._factories[name] = create
        self._backends.update(dict.fromkeys(keys, parse))

    def register_authentication(
        self, backend: str, authentication_type: str | None, resolver: AuthenticationResolver
    ) -> None:
        """Register a compatible backend/auth pair; None means explicitly anonymous.

        Resolvers receive the spec, path, scheme name, and scheme metadata. They
        return the authenticated spec and path, possibly for a different backend.
        ``signed_url`` is reserved; use ``register_signer`` for signing adapters.
        """
        if authentication_type == "signed_url":
            raise ValueError("signed_url authentication is handled by the registry; use register_signer")
        key = (backend, authentication_type)
        if key in self._authentication:
            raise ValueError("authentication registration overlaps an existing registration")
        self._authentication[key] = resolver

    def register_signer(self, backend: str, authorization_api: str, resolver: SigningResolver) -> None:
        """Register a trusted signed-URL adapter for one backend and exact API.

        Adapters receive the spec, path, and flow, and return a spec/path pair.
        They validate the flow and bind credentials with their actual scope. A
        per-object URL signer must not claim container-wide credentials.
        """
        key = (backend, authorization_api)
        if key in self._signers:
            raise ValueError("signer registration overlaps an existing registration")
        self._signers[key] = resolver

    def resolve(
        self, location: "AssetLocation"
    ) -> "tuple[StoreSpec, str, StorageScheme | None, AuthenticationScheme | None]":
        """Select exactly one supported combination, without creating a store."""
        supported = []
        rejected = []
        uri = urlsplit(location.href).scheme.lower() or "file"
        for storage in location.storage_schemes.values() or [None]:
            parser = self._backends.get((uri, _storage_type(storage)))
            if parser is None:
                rejected.append("unsupported URI/storage combination")
                continue
            try:
                spec, path = parser(location.href, storage)
            except ValueError as error:
                rejected.append(str(error))
                continue
            for name, authentication in location.authentication_schemes.items() or [("", None)]:
                kind = _authentication_type(authentication)
                resolver = self._signed_url if kind == "signed_url" else self._authentication.get((spec.backend, kind))
                if resolver is None:
                    rejected.append(f"authentication type {kind!r} is unsupported for {spec.backend}")
                    continue
                try:
                    authenticated, authenticated_path = resolver(spec, path, name, authentication)
                except ValueError as error:
                    rejected.append(str(error))
                    continue
                supported.append((authenticated, authenticated_path, storage, authentication))
        if not supported:
            raise ValueError("; ".join(dict.fromkeys(rejected)))
        if len(supported) > 1:
            raise ValueError("multiple supported storage/authentication combinations are applicable")
        return supported[0]

    def create_store(self, spec: StoreSpec) -> "ObjectStore":
        return self._factories[spec.backend](spec)

    def _signed_url(
        self, spec: StoreSpec, path: str, _name: str, authentication: "AuthenticationScheme | None"
    ) -> tuple[StoreSpec, str]:
        assert authentication is not None
        supported = []
        for flow in authentication.flows:
            signed = flow.signed_url
            if signed is None or flow.oauth2 is not None:
                continue
            resolver = self._signers.get((spec.backend, signed.authorization_api))
            if resolver is None:
                continue
            try:
                supported.append(resolver(spec, path, signed))
            except ValueError:
                continue
        if not supported:
            raise ValueError("unsupported signed URL flow for this backend")
        if len(supported) > 1:
            raise ValueError("multiple supported signed URL flows are applicable")
        return supported[0]


def _storage_type(storage: "StorageScheme | None") -> str | None:
    if storage is None:
        return None
    if storage.has_field("custom_type"):
        return storage.custom_type
    return storage.known_type.name.lower()


def _authentication_type(authentication: "AuthenticationScheme | None") -> str | None:
    if authentication is None:
        return None
    if authentication.has_field("custom_type"):
        return authentication.custom_type
    return authentication.known_type.name.lower()
