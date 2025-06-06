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
    access_key="YOUR_ACCESS_KEY",
    secret_access_key="YOUR_SECRET_ACCESS_KEY",
    cache_directory=Path("./data")
)

downloaded_data = storage_client.download(s2_granule)

print(f"Downloaded granule: {downloaded_data.name} to {downloaded_data}")
print("Contents: ")
for content in downloaded_data.iterdir():
    print(f" - {content.relative_to(downloaded_data)}")
```

## License

Distributed under the MIT License (`The MIT License`).
