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

For interactive job progress in Jupyter notebooks, install `tilebox-workflows[notebook]`.
Without this extra, jobs use their plain-text representation.
For S3 client type information, install `boto3-stubs[s3]` in your development environment.

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

## Workflow-scoped tasks

To submit tasks to a managed workflow, pass its remote reference or a `Workflow` object:

```python
jobs.submit("scoped-job", MyFirstTask(), workflow="my-workflow")

workflow = client.workflows().find("my-workflow")
jobs.submit("another-job", MyFirstTask(), workflow=workflow)
jobs.query(workflows=[workflow, "tilebox:shared-workflow"])
```

The workflow's immutable UUID scopes each root task. A failed reference lookup raises an error without submitting.
Omitting `workflow` keeps roots unscoped, including jobs submitted from inside another task. Existing direct runners
continue to register and execute unscoped tasks.

Task metadata, runner registries, and release contents use `UnboundTaskIdentifier` (name and version).
Submissions and executions use `TaskIdentifier`, which also carries the optional workflow ID. Use `.bind(workflow_id)`
to create an execution identifier and `.unbind()` to recover its implementation identifier.

Children inherit the executing parent's scope. Execution through a legacy unscoped alias therefore produces unscoped
children. The runner handles inheritance internally; `context.submit_subtask()` and `context.submit_subtasks()`
do not expose workflow selection. Cross-workflow and explicitly unscoped child overrides are deferred until the CLI
can distinguish scope-aware workers from workers that need its compatibility adapter.

Both `create_cron_automation()` and `create_storage_event_automation()` accept the same `workflow` parameter as
`jobs.submit()`. Workflow objects expose `id`, `reference`, `project_slug`, and `legacy_task_aliases`; `.slug` remains
a read-only alias for the remote reference. When constructing a `Workflow` directly, use `reference=` instead of
`slug=`. The project slug is not a unique remote selector. Workflows sort by reference, name, and ID, with missing
IDs first; other metadata does not affect ordering.

`client.workflows().create(name, summary)` always creates a scoped-only workflow; creating legacy workflows is not
supported. Existing workflows still expose their alias policy. A `None` policy in a response means the server did not
report that field, rather than reporting `False`.

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

## Reading automation objects

Storage-event tasks can read objects from Amazon S3, Google Cloud Storage, Azure Blob Storage, or the local filesystem:

```python
content = self.trigger.storage.read(self.trigger.location)
```

The method returns bytes. Cloud reads use the credentials configured for the runner.

On macOS, GCS or Azure CLI authentication can emit [gRPC fork diagnostics](https://github.com/grpc/grpc/issues/42293)
even when a read succeeds. These messages alone do not indicate a failed read; do not downgrade gRPC to hide them.

## Documentation

Check out the [Tilebox Workflows documentation](https://docs.tilebox.com/workflows/introduction) for more information.

## License

Distributed under the MIT License (`The MIT License`).
