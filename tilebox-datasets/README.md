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
results = s2a_l1c.query(temporal_extent=("2025-03-01", "2025-06-01"), show_progress=True)
print(f"Found {results.sizes['time']} datapoints")  # Found 220542 datapoints
```

Spatio-temporal queries:

```python
from shapely.geometry import shape

area_of_interest = shape(
    {
        "type": "Polygon",  # coords in lon, lat
        "coordinates": [[[-5, 50], [-5, 56], [-11, 56], [-11, 50], [-5, 50]]],
    }
)
s2a_l1c = sentinel2_msi.collection("S2A_S2MSI1C")
results = s2a_l1c.query(
    temporal_extent=("2025-03-01", "2025-06-01"), spatial_extent=area_of_interest, show_progress=True
)
print(f"Found {results.sizes['time']} datapoints")  # Found 979 datapoints
```

## Enum fields

Define a scalar enum with an ordered list of public strings:

```python
from datetime import UTC, datetime

from tilebox.datasets import field
from tilebox.datasets.data.datasets import DatasetKind

dataset = client.create_or_update_dataset(
    DatasetKind.TEMPORAL,
    "scenes",
    fields=[
        {"name": "processing_level", "type": "enum", "enum_values": ["L1", "L2-SP", "雪"], "queryable": True},
    ],
)
collection = dataset.get_or_create_collection("example")
collection.ingest(
    [
        {"time": datetime(2026, 10, 28, 12, tzinfo=UTC), "processing_level": "L2-SP"},
        {"time": datetime(2026, 10, 28, 13, tzinfo=UTC)},
    ]
)

results = collection.query(
    temporal_extent=("2026-10-28", "2026-10-29"),
    filter=field("processing_level") == "L2-SP",
)
assert results.processing_level.to_numpy().tolist() == ["L2-SP"]
```

Ingestion accepts public strings in records, columns, pandas DataFrames, and xarray Datasets.
Query results contain public strings in object arrays. Missing values remain missing; use xarray's
`isnull()` to identify them. You do not need a Python enum class to create or read a dataset.
Numbers and generated protobuf symbols are not accepted as substitutes for public values.

Scalar enum filters support `==` and `!=`. Combine equality expressions with `|` to match several values.
The server validates values case-sensitively. Comparisons exclude missing values, including `!=`;
include them explicitly with `(field("processing_level") != "L1") | field("processing_level").is_null()`.
Python enum members are not filter literals; use their public string `.value` instead.

Vocabularies contain 1–100 unique, nonempty strings. Empty datasets allow replacing, removing,
renaming, or reordering values. Once a dataset contains data, updates may only append values.
Supply the full field schema when updating a dataset, and re-fetch the dataset after another client
updates its vocabulary. The asynchronous client provides the same enum behavior.

### Repeated enums

Add `"repeated": True` to define lists of enum values, including queryable tags:

```python
fields = [
    {
        "name": "use_cases",
        "type": "enum",
        "enum_values": ["agriculture", "defense", "wind-power"],
        "repeated": True,
        "queryable": True,
    },
]
dataset = client.create_or_update_dataset(DatasetKind.TEMPORAL, "tagged_scenes", fields)
collection = dataset.get_or_create_collection("example")
collection.ingest(
    [
        {"time": datetime(2026, 10, 28, 12, tzinfo=UTC), "use_cases": ["defense", "agriculture", "defense"]},
    ]
)
results = collection.query(
    temporal_extent=("2026-10-28", "2026-10-29"),
    filter=field("use_cases").contains("defense"),
)

# Alternative membership filters:
all_tags = field("use_cases").contains_all(["defense", "agriculture"])
any_tag = field("use_cases").contains_any(["defense", "wind-power"])
without_defense = ~field("use_cases").contains("defense")
```

The backend removes duplicates during ingestion, preserving first-occurrence order. The example
stores `["defense", "agriculture"]`. Ingest lists of public strings through records, columns, or pandas;
xarray results can also be ingested again. Results use the existing padded repeated-field layout:
`use_cases(time, n_use_cases)`, with missing padding. If all returned lists are empty, the variable is omitted.

Repeated enums use membership filters, not `==`, `!=`, or null checks. Combine predicates with `&`, `|`,
and `~`. Membership treats omitted and empty lists as the empty set and never returns null.
Consequently, `without_defense` includes untagged rows. `contains_all([])` matches every row;
`contains_any([])` matches none. Each predicate accepts up to 100 nonempty public strings, counting
duplicates toward that limit. The server checks vocabulary membership and whether the field is queryable.

## Documentation

Check out the [Tilebox Datasets documentation](https://docs.tilebox.com/datasets/introduction) for more information.

## License

Distributed under the MIT License (`The MIT License`).
