from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from platform import python_version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyqwest import HTTPTransport


@dataclass
class StorageURLs:
    data: str
    quicklook: str | None


async def login(storage_provider: str, auth: tuple[str, str]) -> HTTPTransport:
    match storage_provider:
        case "ASF":
            return await _asf_login(auth)

    raise ValueError(f"Unknown storage provider: '{storage_provider}'")


# ASF - Alaska Satellite Facility
_ASF_URL = "https://datapool.asf.alaska.edu"


async def _asf_login(auth: tuple[str, str]) -> HTTPTransport:
    """
    Create an authenticated HTTP transport for downloading data from the ASF server.

    Args:
        auth: Tuple of username and password for the ASF server

    Raises:
        ValueError: If the username/password or token authentication is invalid.

    Returns:
        HTTPTransport: The cookie-bearing transport. The caller owns closing it.
    """
    login_url = "https://urs.earthdata.nasa.gov/oauth/authorize"
    user_agent = "; ".join(
        [
            f"Python/{python_version()}",
            "requests/2.31.0",  # not actually dependencies, so we can hardcode something
            "asf_search/6.6.3",  # same for asf_search
        ]
    )
    client_id = "asf_search_v6.6.3"

    headers = {
        "User-Agent": user_agent,
        "Client-Id": client_id,
        "Authorization": "Basic " + b64encode(f"{auth[0]}:{auth[1]}".encode("latin-1")).decode("ascii"),
    }

    from pyqwest import Client, HTTPTransport  # noqa: PLC0415

    transport = HTTPTransport(tls_include_system_certs=True, enable_cookie_store=True, follow_redirects=True)
    try:
        # Send credentials only to Earthdata. Subsequent downloads use the authenticated cookies.
        response = await Client(transport).get(
            login_url,
            headers=headers,
            params={
                "client_id": "BO_n7nTIlMljdvU6kRRB3g",
                "response_type": "code",
                "redirect_uri": "https://auth.asf.alaska.edu/login",
            },
        )
    except BaseException:
        await transport.aclose()
        raise
    if response.status >= 400:
        await transport.aclose()
        if response.status == 401:
            raise ValueError("Invalid username or password.")
        raise ValueError(f"ASF login failed with HTTP {response.status}")
    return transport
