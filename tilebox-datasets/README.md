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
</div>

<p align="center">
  <a href="https://docs.tilebox.com/datasets/introduction"><b>Documentation</b></a>
  |
  <a href="https://console.tilebox.com/"><b>Console</b></a>
  |
  <a href="https://tilebox.com/discord"><b>Discord</b></a>
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

# create your API key at
# https://console.tilebox.com
client = Client(token="YOUR_TILEBOX_API_KEY")
```

Explore datasets:

```python
datasets = client.datasets()
print(datasets)

sentinel1_sar = datasets.open_data.copernicus.sentinel1_sar
collections = sentinel1_sar.collections()
print(collections)
```

Load data:

```python
s1a_raw = collections["S1A_IW_RAW__0S"]
interval = ("2017-01-01", "2023-01-01")
raw_data = s1a_raw.load(interval, show_progress=True)
print(raw_data)
```

```plaintext
<xarray.Dataset> Size: 725MB
Dimensions:                (time: 1109597, latlon: 2)
Coordinates:
    ingestion_time         (time) datetime64[ns] 9MB 2024-06-21T11:03:33.8524...
    id                     (time) <U36 160MB '01595763-bae7-a646-99a5-d7f40d7...
  * time                   (time) datetime64[ns] 9MB 2017-01-01T00:17:50.8230...
  * latlon                 (latlon) <U9 72B 'latitude' 'longitude'
Data variables: (12/30)
    granule_name           (time) object 9MB 'S1A_IW_RAW__0SSV_20170101T00175...
    processing_level       (time) <U2 9MB 'L0' 'L0' 'L0' 'L0' ... 'L0' 'L0' 'L0'
    satellite              (time) object 9MB 'SENTINEL-1' ... 'SENTINEL-1'
    flight_direction       (time) <U10 44MB 'ASCENDING' ... 'ASCENDING'
    product_type           (time) object 9MB 'IW_RAW__0S' ... 'IW_RAW__0S'
    copernicus_id          (time) <U36 160MB 'f3f6ec28-0f72-5d28-9e14-93f96b3...
    ...                     ...
    acquisition_mode       (time) <U2 9MB 'IW' 'IW' 'IW' 'IW' ... 'IW' 'IW' 'IW'
```

## Documentation

Check out the [Tilebox Datasets documentation](https://docs.tilebox.com/datasets/introduction) for more information.

## License

Distributed under the MIT License (`The MIT License`).
