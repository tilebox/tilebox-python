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
</div>

<p align="center">
  <a href="https://docs.tilebox.com/workflows/introduction"><b>Documentation</b></a>
  |
  <a href="https://console.tilebox.com/"><b>Console</b></a>
  |
  <a href="https://tilebox.com/discord"><b>Discord</b></a>
</p>

# Tilebox Workflows

Tilebox Workflows, or the Tilebox workflow orchestrator is a parallel processing engine that allows an intuitive creation of dynamic tasks that can be parallelized out of the box and executed across compute environments or on-premise as well as in auto-scaling clusters in public clouds.

## Quickstart

Install using `pip`:

```bash
pip install tilebox-workflows
```

Create a task:

```python
from tilebox.workflows import Task

class MyFirstTask(Task):
  def execute(self):
    print("Hello World from my first Tilebox task!")
```

Submit a job

```python
from tilebox.workflows import Client

# create your API key at
# https://console.tilebox.com
client = Client(token="YOUR_TILEBOX_API_KEY")

jobs = client.jobs()
jobs.submit("my-very-first-job", "some-compute-cluster", MyFirstTask())
```

And run it:

```python
runner = client.runner("some-compute-cluster", tasks=[MyFirstTask])
runner.run_all()
```

## Documentation

Check out the [Tilebox Workflows documentation](https://docs.tilebox.com/workflows/introduction) for more information.

## License

Distributed under the MIT License (`The MIT License`).
