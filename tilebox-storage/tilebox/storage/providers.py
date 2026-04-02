from dataclasses import dataclass
from platform import python_version

from niquests import AsyncSession


@dataclass
class StorageURLs:
    data: str
    quicklook: str | None


async def login(storage_provider: str, auth: tuple[str, str]) -> AsyncSession:
    match storage_provider:
        case "ASF":
            return await _asf_login(auth)

    raise ValueError(f"Unknown storage provider: '{storage_provider}'")


# ASF - Alaska Satellite Facility
_ASF_URL = "https://datapool.asf.alaska.edu"


async def _asf_login(auth: tuple[str, str]) -> AsyncSession:
    """
    Create an HTTP session for downloading data from the ASF server.

    Args:
        auth: Tuple of username and password for the ASF server

    Raises:
        ValueError: If the username/password or token authentication is invalid.

    Returns:
        AsyncSession: The authenticated async session to use for downloading data.
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
    }

    client = AsyncSession(auth=auth, headers=headers)
    response = await client.get(
        login_url,
        allow_redirects=True,
        params={
            "client_id": "BO_n7nTIlMljdvU6kRRB3g",
            "response_type": "code",
            "redirect_uri": "https://auth.asf.alaska.edu/login",
        },
    )
    if response.status_code == 401:
        await client.close()
        raise ValueError("Invalid username or password.")
    return client
