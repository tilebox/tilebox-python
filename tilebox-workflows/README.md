# Tilebox Workflows

![PyPI - Version](https://img.shields.io/pypi/v/tilebox-workflows.svg?style=flat-square&label=version&color=f43f5e)
![Python](https://img.shields.io/pypi/pyversions/tilebox-workflows.svg?style=flat-square&logo=python&color=f43f5e&logoColor=f43f5e)

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
jobs.submit("my-very-first-job", MyFirstTask(), "some-compute-cluster")
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
