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
  <a href="https://docs.tilebox.com/workflows/introduction"><b>Documentation</b></a>
  |
  <a href="https://console.tilebox.com/"><b>Console</b></a>
  |
  <a href="https://examples.tilebox.com/"><b>Example Gallery</b></a>
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

# create your API key at https://console.tilebox.com
client = Client(token="YOUR_TILEBOX_API_KEY")

jobs = client.jobs()
jobs.submit("my-very-first-job", MyFirstTask())
```

And run it:

```python
runner = client.runner(tasks=[MyFirstTask])
runner.run_all()
```

## Concurrent worker execution

A worker runtime can execute multiple tasks concurrently in one Python process. Each execution receives a newly
deserialized task instance and its own `ExecutionContext`, including task-local subtask and progress state. The
`RunnerContext`, configured `JobCache`, and any class or module state are process-level resources shared by those
executions.

Custom runner contexts, caches, and shared task state must therefore support concurrent access from multiple threads.
Asynchronous task executions may also run on different event loops. Configure and register these resources before the
worker starts; do not mutate runner configuration while tasks are executing. Compound cache operations are not atomic
unless the cache implementation explicitly provides that guarantee.

Concurrency in one runtime avoids repeated process initialization and allows overlapping I/O or native code that
releases Python's GIL. CPU-bound Python code still needs multiple runtime processes for parallel execution.

## Documentation

Check out the [Tilebox Workflows documentation](https://docs.tilebox.com/workflows/introduction) for more information.

## License

Distributed under the MIT License (`The MIT License`).
