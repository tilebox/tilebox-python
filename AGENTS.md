# AGENTS.md

## Repository Purpose

This repository is the Python monorepo for Tilebox SDK packages. It is organized as a `uv` workspace with multiple publishable packages that share common development tooling and a shared dependency graph.

## Monorepo Architecture

The workspace contains four implementation packages and a compatibility package:

- `tilebox-core`: Public `tilebox.query` value types and `tilebox.errors` exceptions; private shared infrastructure, generated messages, conversions, transports, pagination, replay, and concurrency helpers under `_tilebox`. Only this distribution packages `_tilebox`.
- `tilebox-grpc`: Empty compatibility package depending on `tilebox-core>=0.68.0`, retained for one release.
- `tilebox-datasets`: Datasets SDK (`tilebox.datasets`) with sync + async clients, query/data model helpers, protobuf conversion, and generated datasets-related protobuf stubs.
- `tilebox-workflows`: Workflows SDK (`tilebox.workflows`) with job/cluster/automation clients, task model + runner, observability/tracing, and generated workflows protobuf stubs.
- `tilebox-storage`: Storage SDK (`tilebox.storage`) for provider-specific payload downloads (ASF, Copernicus, Umbra, Landsat, local FS), built mostly on async internals with sync wrappers.

Design choices to keep in mind:

- Namespace package layout: multiple packages contribute modules under shared top-level namespaces like `tilebox.*`.
- Public clients call generated Connect clients directly and convert protobuf messages to domain objects.
- Sync + async parity: datasets has native blocking and async clients with shared conversion helpers.
- External API communication uses native Connect RPC clients and protobuf-py messages.

## Developer Tooling

Use `uv` for all local development.

### Setup

```bash
uv sync --all-packages
```

### Test Commands

```bash
# All packages with coverage aggregation
./tests.sh

# Single package examples
uv run --package tilebox-datasets pytest tilebox-datasets
uv run --package tilebox-workflows pytest tilebox-workflows
uv run --package tilebox-storage pytest tilebox-storage
uv run --no-sync pytest tilebox-core
```

### Lint / Format / Type Check

```bash
uv run ruff format .
uv run ruff check --fix .
uv run ty check
```

### Pre-commit

```bash
uv run prek run --all-files
```

Pre-commit hooks include YAML checks, EOF fixer, `sync-with-uv`, Ruff, and `ty`.

## Code Style And Paradigms

- Python target: `>=3.11`; supported versions are 3.11 through 3.14.
- Linting/formatting is Ruff-based and fairly strict (`select = ["ALL"]`) with explicit ignores configured in root `pyproject.toml`.
- Type hints are used broadly across public APIs and internals.
- Prefer dataclasses and explicit domain objects for request/response translation.
- Keep transport and error translation in `_tilebox`; request construction and response conversion belong in clients.
- Workflows uses a lightweight structured facade over stdlib logging, with separate internal and task channels;
- Tests use `pytest`, with async coverage (`pytest-asyncio`) and property-based testing (`hypothesis`) in multiple packages.

### Import-Time Discipline

- Keep `tilebox.workflows` task-authoring imports light. Release runners create fresh virtual environments, so avoid
  importing heavy optional/runtime dependencies (`pandas`, `numpy`, `xarray`, cloud SDKs, `ipywidgets`, OpenTelemetry
  SDK/exporters, cache backends) from package `__init__` modules or core `Runner`/`Task` import paths.
- Prefer lazy imports inside the methods that actually need those dependencies. Module-level `__getattr__` aliases are
  acceptable for public package aliases and are supported by Python 3.7+.

## Protobuf And Generated Code

Generated files live under paths such as:

- `tilebox-datasets/tilebox/datasets/v1/*_pb.py`
- `tilebox-datasets/tilebox/datasets/stac/v1/*_pb.py`
- `tilebox-core/_tilebox/proto/tilebox/v1/*_pb.py`
- `tilebox-workflows/tilebox/workflows/v1/*_pb.py`
- `tilebox-workflows/tilebox/workflows/_otel/opentelemetry/proto/**`

Regenerate protobuf code with:

```bash
./tools/generate-protobuf.sh
```

This uses `buf.gen.yaml` with pinned local plugins and import mappings.
The script strips upstream trailing whitespace with Ruff and places the generated modules in their owning packages.

### Important Boundary: API Schema Source Of Truth

- Many protobuf contracts are sourced from the separate `api` repository/module (`buf.build/tilebox/api`, with optional local `../api` input in buf configs).
- Do **not** hand-edit generated `*_pb.py` or `*_connect.py` files.
- If a requested change requires modifying protobuf schema/contracts, that change must be made in the `api` repo first.
- Whenever schema/proto edits are needed, ask the developer to point you to the `api` repo so those changes can be implemented there and then regenerated here.
