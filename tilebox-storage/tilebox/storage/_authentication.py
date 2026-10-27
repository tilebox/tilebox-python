"""Built-in authentication plugins; credentials are never inferred from a URI."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from tilebox.storage._registry import Registry, StoreSpec

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any

    from obstore.store import S3Credential, S3CredentialProvider

    from tilebox.datasets.stac.v1.authentication_pb import AuthenticationScheme


def register_authentication(registry: Registry, s3_credentials: Mapping[str, "S3CredentialProvider"]) -> None:
    from tilebox.storage._planetary_computer import bind_credentials  # noqa: PLC0415

    for backend in ("file", "http", "s3", "gcs", "azure"):
        registry.register_authentication(backend, None, _anonymous)
    registry.register_authentication("s3", "s3", _S3Authentication(s3_credentials))
    registry.register_signer("azure", "https://planetarycomputer.microsoft.com/api/sas/v1/sign", bind_credentials)


def _anonymous(
    spec: StoreSpec, path: str, _name: str, _authentication: "AuthenticationScheme | None"
) -> tuple[StoreSpec, str]:
    return spec, path


@dataclass(frozen=True, eq=False)
class _S3Credentials:
    # Identity equality supports even unhashable caller providers, without using secret values as keys.
    provider: "S3CredentialProvider" = field(repr=False)

    def __call__(self) -> "S3Credential | Coroutine[Any, Any, S3Credential]":
        return self.provider()


class _S3Authentication:
    def __init__(self, providers: Mapping[str, "S3CredentialProvider"]) -> None:
        bindings = {id(provider): _S3Credentials(provider) for provider in providers.values()}
        self._credentials = {name: bindings[id(provider)] for name, provider in providers.items()}

    def __call__(
        self, spec: StoreSpec, path: str, name: str, _authentication: "AuthenticationScheme | None"
    ) -> tuple[StoreSpec, str]:
        provider = self._credentials.get(name)
        if provider is None:
            raise ValueError("S3 authentication requires an explicitly configured credential provider")
        return replace(spec, credential_provider=provider), path
