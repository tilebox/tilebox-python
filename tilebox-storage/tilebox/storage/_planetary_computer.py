"""Planetary Computer metadata validation and lazy Azure SAS credentials."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from tilebox.storage._registry import StoreSpec

if TYPE_CHECKING:
    from niquests import AsyncResponse, AsyncSession, Response
    from obstore.store import AzureSASToken

    from tilebox.datasets.datasets.stac.v1.authentication_pb import SignedURLFlow


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
        from niquests import AsyncSession  # noqa: PLC0415
        from niquests.exceptions import RequestException  # noqa: PLC0415

        # The session belongs to this fetch, not to the storage client's lifetime or event loop.
        async with AsyncSession() as session:
            session.trust_env = False  # Never forward netrc credentials to the signing service.
            try:
                url = f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{self.account}/{self.container}"
                response = await _request_token(session, url)
            except RequestException:
                raise ValueError("Planetary Computer token request failed") from None
            if response.status_code != 200:
                raise ValueError("Planetary Computer token endpoint did not return HTTP 200")
            try:
                return _parse_credentials(response.json())
            except (KeyError, TypeError, ValueError):
                # Neither response bodies nor HTTP/JSON errors are safe to include: they may contain SAS tokens.
                raise ValueError("Planetary Computer returned invalid or expired SAS credentials") from None


def _is_transient(error: BaseException) -> bool:
    from niquests.exceptions import ConnectionError as HTTPConnectionError  # noqa: PLC0415
    from niquests.exceptions import HTTPError, Timeout  # noqa: PLC0415

    if isinstance(error, (HTTPConnectionError, Timeout)):
        return True
    if isinstance(error, HTTPError) and error.response is not None:
        status = error.response.status_code or 0
        return status == 429 or 500 <= status < 600
    return False


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5),
    reraise=True,
)
async def _request_token(session: "AsyncSession", url: str) -> "Response | AsyncResponse":
    response = await session.get(url, timeout=30, allow_redirects=False)
    response.raise_for_status()
    return response


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
