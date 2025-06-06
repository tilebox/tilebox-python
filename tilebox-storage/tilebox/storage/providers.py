from dataclasses import dataclass
from platform import python_version

from httpx import AsyncClient


@dataclass
class StorageURLs:
    data: str
    quicklook: str | None


def download_urls(storage_provider: str, granule_name: str, processing_level: str) -> StorageURLs:
    match storage_provider:
        case "ASF":
            return _asf_download_urls(granule_name, processing_level)

    raise ValueError(f"Unknown storage provider: '{storage_provider}'")


async def login(storage_provider: str, auth: tuple[str, str]) -> AsyncClient:
    match storage_provider:
        case "ASF":
            return await _asf_login(auth)

    raise ValueError(f"Unknown storage provider: '{storage_provider}'")


# ASF - Alaska Satellite Facility
_ASF_URL = "https://datapool.asf.alaska.edu"


def _asf_download_urls(granule_name: str, processing_level: str) -> StorageURLs:
    platform = granule_name.split("_")[0]
    file_name = granule_name
    quicklook = None
    if platform in ("E1", "E2"):
        quicklook = f"{_ASF_URL}/BROWSE/{platform}/{granule_name}.jpg"
        file_name = file_name.replace("STD_", f"STD_{processing_level}_")

    if platform in ("S1A", "S1B"):
        processing_level = "RAW" if processing_level == "L0" else processing_level
        platform = platform.replace("S1", "S")

    data = f"{_ASF_URL}/{processing_level}/{platform}/{file_name}.zip"
    return StorageURLs(data, quicklook)


async def _asf_login(auth: tuple[str, str]) -> AsyncClient:
    """
    Create a http session for downloading data from the ASF server.

    Args:
        auth: Tuple of username and password for the ASF server

    Raises:
        ValueError: If the username/password or token authentication is invalid.

    Returns:
        AsyncClient: The authenticated Async Client to use for downloading data.
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

    client = AsyncClient(auth=auth, headers=headers)
    response = await client.get(
        login_url,
        follow_redirects=True,
        params={
            "client_id": "BO_n7nTIlMljdvU6kRRB3g",
            "response_type": "code",
            "redirect_uri": "https://auth.asf.alaska.edu/login",
        },
    )
    if response.status_code == 401:
        raise ValueError("Invalid username or password.")
    return client
