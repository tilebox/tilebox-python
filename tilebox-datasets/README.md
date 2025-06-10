<h1 align="center">
  <img src="https://storage.googleapis.com/tbx-web-assets-2bad228/banners/tilebox-banner.svg" alt="Tilebox Logo">
  <br>
</h1>

<div align="center">
  <a href="https://pypi.org/project/tilebox-datasets/">
    <img src="https://img.shields.io/pypi/v/tilebox-datasets.svg?style=flat-square&label=version&color=f43f5e" alt="PyPi Latest Release badge"/>
  </a>
  <a href="https://pypi.org/project/tilebox-datasets/">
    <img src="https://img.shields.io/pypi/pyversions/tilebox-datasets.svg?style=flat-square&logo=python&color=f43f5e&logoColor=f43f5e" alt="Required Python Version badge"/>
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
  <a href="https://docs.tilebox.com/datasets/introduction"><b>Documentation</b></a>
  |
  <a href="https://console.tilebox.com/"><b>Console</b></a>
  |
  <a href="https://examples.tilebox.com/"><b>Example Gallery</b></a>
</p>

# Tilebox Datasets

Access satellite data using the [Tilebox](https://tilebox.com) datasets python client powered by gRPC and Protobuf.

## Quickstart

Install using `pip`:

```bash
pip install tilebox-datasets
```

Instantiate a client:

```python
from tilebox.datasets import Client

# create your API key at https://console.tilebox.com
client = Client(token="YOUR_TILEBOX_API_KEY")
```

Explore datasets and collections:

```python
datasets = client.datasets()
print(datasets)

sentinel2_msi = client.dataset("open_data.copernicus.sentinel2_msi")
collections = sentinel2_msi.collections()
print(collections)
```

Query data:

```python
s2a_l1c = sentinel2_msi.collection("S2A_S2MSI1C")
results = s2a_l1c.query(
  temporal_extent=("2025-03-01", "2025-06-01"),
  show_progress=True
)
print(f"Found {results.sizes['time']} datapoints")  # Found 220542 datapoints
```

Spatio-temporal queries:

```python
from shapely.geometry import shape

area_of_interest = shape({
    "type": "Polygon",  # coords in lon, lat
    "coordinates": [[[-5, 50], [-5, 56], [-11, 56], [-11, 50], [-5, 50]]]}
)
s2a_l1c = sentinel2_msi.collection("S2A_S2MSI1C")
results = s2a_l1c.query(
  temporal_extent=("2025-03-01", "2025-06-01"),
  spatial_extent=area_of_interest,
  show_progress=True
)
print(f"Found {results.sizes['time']} datapoints")  # Found 979 datapoints
```

## Documentation

Check out the [Tilebox Datasets documentation](https://docs.tilebox.com/datasets/introduction) for more information.

## License

Distributed under the MIT License (`The MIT License`).
