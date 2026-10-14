<h1 align="center">
  <img src="https://storage.googleapis.com/tbx-web-assets-2bad228/banners/tilebox-banner.svg" alt="Tilebox Logo">
  <br>
</h1>

<div align="center">
  <a href="https://pypi.org/project/tilebox-storage/">
    <img src="https://img.shields.io/pypi/v/tilebox-storage.svg?style=flat-square&label=version&color=f43f5e" alt="PyPi Latest Release badge"/>
  </a>
  <a href="https://pypi.org/project/tilebox-storage/">
    <img src="https://img.shields.io/pypi/pyversions/tilebox-storage.svg?style=flat-square&logo=python&color=f43f5e&logoColor=f43f5e" alt="Required Python Version badge"/>
  </a>
  <a href="https://github.com/tilebox/tilebox-python/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/tilebox/tilebox-python.svg?style=flat-square&color=f43f5e" alt="MIT License"/>
  </a>
  <a href="https://github.com/tilebox/tilebox-python/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/tilebox/tilebox-python/main.yml?style=flat-square&color=f43f5e" alt="Build Status"/>
  </a>
  <a href="https://tilebox.com/discord">
    <img src="https://img.shields.io/badge/Discord-%235865F2.svg?style=flat-square&logo=discord&logoColor=white" alt="Join us on Discord"/>
  </a>
</div>

<p align="center">
  <a href="https://docs.tilebox.com/"><b>Documentation</b></a>
  |
  <a href="https://console.tilebox.com/"><b>Console</b></a>
  |
  <a href="https://examples.tilebox.com/"><b>Example Gallery</b></a>
</p>

# Tilebox Storage

Download satellite payload data for your [Tilebox datasets](https://pypi.org/project/tilebox-datasets/).

## Quickstart

Install using `pip`:

```bash
pip install tilebox-storage tilebox-datasets
```

Fetch a datapoint to download the payload data for:

```python
from tilebox.datasets import Client


# Creating clients
client = Client(token="YOUR_TILEBOX_API_KEY")
datasets = client.datasets()

# Choosing the dataset and collection
s2_dataset = datasets.open_data.copernicus.sentinel2_msi
collections = s2_dataset.collections()
collection = collections["S2A_S2MSI2A"]

# Loading metadata
s2_data = collection.load(("2024-08-01", "2024-08-02"), show_progress=True)

# Let's download the first granule
s2_granule = s2_data.isel(time=0)
```

Then download the payload data using a storage client:

```python
from pathlib import Path
from tilebox.storage import CopernicusStorageClient

# Check out the Copernicus Dataspace S3 documentation at
# https://documentation.dataspace.copernicus.eu/APIs/S3.html
# to learn how to get your access key and secret access key
storage_client = CopernicusStorageClient(
    access_key="YOUR_ACCESS_KEY", secret_access_key="YOUR_SECRET_ACCESS_KEY", cache_directory=Path("./data")
)

downloaded_data = storage_client.download(s2_granule)

print(f"Downloaded granule: {downloaded_data.name} to {downloaded_data}")
print("Contents: ")
for content in downloaded_data.iterdir():
    print(f" - {content.relative_to(downloaded_data)}")
```

## Planetary Computer assets

The asynchronous asset client reads Planetary Computer assets through the same API as public assets:

```python
from tilebox.datasets.assets import AssetCollection
from tilebox.storage.aio import Client

assets = AssetCollection.from_datapoint(datapoint)
storage = Client()

resolved = storage.resolve(assets["red"])  # Local metadata validation only; no network requests.
geotiff = await storage.open_geotiff(assets["red"])
metadata = await storage.read_bytes(assets["mtl.json"], max_bytes=1_000_000)
await storage.download(assets["red"], "data/red.tif")
```

The asset must declare the Planetary Computer `signedUrl` flow for
`https://planetarycomputer.microsoft.com/api/sas/v1/sign` (GET, an `href` query parameter,
and an `href` response field). HTTPS locations also need Microsoft Azure storage metadata.
The client checks the account and container against any supplied storage metadata.
Planetary Computer is the only built-in signing service; unknown APIs are rejected.

The first read fetches a container-scoped SAS token automatically. Assets with the same account,
container, and credential binding share an object store. Descriptions and unused flows do not
split the cache. Obstore caches credentials and
refreshes them on demand near expiry. `resolved.href` stays unsigned; callers do not need to manage
tokens or close a session. Token requests use `niquests` and bounded async Tenacity retries.

Use async obstore operations if accessing `resolved.store` directly. Download NetCDF and HDF assets
with `download()` before opening them locally; `open_geotiff()` only supports GeoTIFF assets.

## Asset locations and credentials

The asset client supports local paths and `file`, `s3`, `gs`/`gcs`, `az`/`azure`, `abfs`/`abfss`,
and HTTP(S) locations. Azure forms are:

- `az://account/container/key` (also `azure`)
- `abfs://container@account.dfs.core.windows.net/key` (also `abfss`)
- `abfs://container/key` with the account in storage metadata (also `abfss`)
- `https://account.blob.core.windows.net/container/key` with Azure storage metadata

These Azure forms share stores and signing credentials. A resolved `path` can be an object key
or dataset prefix; it is never a full URL. This permits multi-key readers such as a future
`open_zarr()` without putting the prefix into the store cache key. No Zarr reader is included yet.

Locations without authentication metadata use unsigned cloud requests, even when credentials
are present in the environment. Obstore still reads environment configuration when constructing
stores; `skip_signature` disables request authentication, not environment configuration parsing.
Declared but unsupported authentication fails resolution rather than falling back to anonymous
access. The client tries supported alternate locations during resolution, not after read failures.

S3 authentication requires an explicitly supplied provider, keyed by the location's authentication
scheme name. For example, this opts into boto3's credential discovery on the first read:

```python
import asyncio
from obstore.auth.boto3 import Boto3CredentialProvider
from tilebox.storage.aio import Client


async def aws_credentials():
    def fetch():
        return Boto3CredentialProvider()()

    return await asyncio.to_thread(fetch)


storage = Client(s3_credentials={"aws": aws_credentials})
```

HTTP query parameters remain part of the request URL and store identity, rather than being
encoded into the object key. They cannot be discarded: a parameter such as `versionId` may
select different data. Prefer normalized native locations in datapoints for cloud-specific
authentication; the client does not infer S3 or GCS bucket layouts from arbitrary HTTPS URLs.

Resolution uses an internal registry of supported backends and authentication flows; there is no
public plugin registration API. Unsupported combinations are filtered before ambiguity is checked.
Two supported combinations or signing flows require the caller to disambiguate the metadata.

## License

Distributed under the MIT License (`The MIT License`).
