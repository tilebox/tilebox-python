<h1 align="center">
  <img src="https://storage.googleapis.com/tbx-web-assets-2bad228/banners/tilebox-banner.svg" alt="Tilebox Logo">
  <br>
</h1>

<div align="center">
  <a href="https://pypi.org/project/tilebox-workflows/">
    <img src="https://img.shields.io/pypi/v/tilebox-workflows.svg?style=flat-square&label=version&color=f43f5e" alt="PyPi Latest Release badge"/>
  </a>
  <a href="https://pypi.org/project/tilebox-workflows/">
    <img src="https://img.shields.io/pypi/pyversions/tilebox-workflows.svg?style=flat-square&logo=python&color=f43f5e&logoColor=f43f5e" alt="Required Python Version badge"/>
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

# Tilebox Python

Python clients for [Tilebox](https://tilebox.com) - a framework for space data management and workflow orchestration.

## Install

```bash
pip install tilebox-datasets tilebox-workflows tilebox-storage
```

> [!TIP]
> For new projects we recommend using [uv](https://docs.astral.sh/uv/) - `uv add tilebox-datasets tilebox-workflows tilebox-storage`. Additional installation options are available [in our docs](https://docs.tilebox.com/sdks/python/install).

## Documentation

Documentation is available at [docs.tilebox.com](https://docs.tilebox.com).

## Getting started

### Tilebox Datasets

Structured and high-performance satellite metadata storage, indexing and querying. [See documentation](https://docs.tilebox.com/datasets/introduction)

```python
from tilebox.datasets import Client
from shapely.geometry import shape

# create your API key at https://console.tilebox.com
client = Client(token="YOUR_TILEBOX_API_KEY")
datasets = client.datasets()
print(datasets)

sentinel2_msi = client.dataset("open_data.copernicus.sentinel2_msi")
collections = sentinel2_msi.collections()
print(collections)

area_of_interest = shape({
    "type": "Polygon",  # coords in lon, lat
    "coordinates": [[[-5, 50], [-5, 56], [-11, 56], [-11, 50], [-5, 50]]]}
)
s2a_l1c = sentinel2_msi.collection("S2A_S2MSI1C")
results = s2a_l1c.query(
  temporal_extent=("2022-07-13", "2022-07-13T02:00"),
  spatial_extent=area_of_interest,
  show_progress=True
)
print(f"Found {results.sizes['time']} datapoints")  # Found 979 datapoints
```


### Tilebox Workflows

A parallel processing engine to simplify the creation of dynamic tasks that can be executed across various computing environments, including on-premise and auto-scaling clusters in public clouds.

```python
from tilebox.workflows import Client, Task

class MyFirstTask(Task):
  def execute(self):
    print("Hello World from my first Tilebox task!")


# create your API key at https://console.tilebox.com
client = Client(token="YOUR_TILEBOX_API_KEY")

# submit a job
jobs = client.jobs()
jobs.submit("my-very-first-job", MyFirstTask())

# and run it
runner = client.runner(tasks=[MyFirstTask])
runner.run_all()
```

## Contributing

Contributions are welcome! Please see the [contributing guide](https://github.com/tilebox/tilebox-python/blob/main/CONTRIBUTING.md) for more information.

You can also join us on [Discord](https://tilebox.com/discord) if you have any questions or want to share your ideas.

## License

Distributed under the MIT License (`The MIT License`).
