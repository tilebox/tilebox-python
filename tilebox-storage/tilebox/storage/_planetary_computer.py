"""Planetary Computer metadata validation and lazy Azure SAS credentials."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl

from tenacity import RetryError, retry, retry_if_exception_type, retry_if_result, stop_after_attempt, wait_exponential

from tilebox.storage._registry import StoreSpec

if TYPE_CHECKING:
    from obstore.store import AzureSASToken
    from pyqwest import Client, FullResponse

    from tilebox.datasets.stac.v1.authentication_pb import SignedURLFlow


def bind_credentials(spec: StoreSpec, path: str, signed: "SignedURLFlow") -> tuple[StoreSpec, str]:
    """Adapt the advertised signing flow to container-scoped Azure credentials."""
    if signed.method != "GET" or signed.response_field != "href":
        raise ValueError("unsupported Planetary Computer signed URL flow")
    parameter = signed.parameters.get("href")
    if (
        parameter is None
        or parameter.location != "query"
        or any(parameter.required for name, parameter in signed.parameters.items() if name != "href")
    ):
        raise ValueError("unsupported Planetary Computer signing parameters")

    account = str(dict(spec.options)["account_name"])
    return replace(spec, credential_provider=_PlanetaryComputerCredentialProvider(account, spec.root)), path


@dataclass(frozen=True)
class _PlanetaryComputerCredentialProvider:
    account: str
    container: str

    async def __call__(self) -> "AzureSASToken":
        from pyqwest import Client, HTTPTransport, ReadError, RemoteProtocolError, TooManyRedirects, WriteError  # noqa: PLC0415

        # The transport belongs to this fetch. Pyqwest does not load netrc credentials.
        async with HTTPTransport(tls_include_system_certs=True, follow_redirects=True, timeout=30) as transport:
            try:
                url = f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{self.account}/{self.container}"
                response = await _request_token(Client(transport), url)
            except (
                ConnectionError,
                TimeoutError,
                ReadError,
                WriteError,
                RemoteProtocolError,
                TooManyRedirects,
                RetryError,
            ):
                raise ValueError("Planetary Computer token request failed") from None
            if response.status != 200:
                raise ValueError("Planetary Computer token endpoint did not return HTTP 200")
            try:
                return _parse_credentials(response.json())
            except (KeyError, TypeError, ValueError):
                # Neither response bodies nor HTTP/JSON errors are safe to include: they may contain SAS tokens.
                raise ValueError("Planetary Computer returned invalid or expired SAS credentials") from None


@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
    | retry_if_result(lambda response: response.status == 429 or 500 <= response.status < 600),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5),
    reraise=True,
)
async def _request_token(client: "Client", url: str) -> "FullResponse":
    return await client.get(url)


def _parse_credentials(payload: Any) -> "AzureSASToken":
    token = payload["token"]
    if not isinstance(token, str) or not token or any(char.isspace() for char in token):
        raise ValueError("invalid SAS token")
    fields = dict(parse_qsl(token.lstrip("?"), strict_parsing=True))
    if not fields.get("sig") or not fields.get("se"):
        raise ValueError("invalid SAS token")
    expires_at = datetime.fromisoformat(payload["msft:expiry"])
    if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
        raise ValueError("invalid SAS expiry")
    return {"sas_token": token, "expires_at": expires_at.astimezone(UTC)}
