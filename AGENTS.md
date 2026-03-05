# AGENTS.md

## Repository Purpose

This repository is the Python monorepo for Tilebox SDK packages. It is organized as a `uv` workspace with multiple publishable packages that share common development tooling and a shared dependency graph.

## Monorepo Architecture

The workspace is split into four packages:

- `tilebox-grpc`: Shared low-level gRPC/protobuf plumbing (`_tilebox.grpc`), sync and async channel handling, error mapping, pagination, replay, and async-to-sync helpers.
- `tilebox-datasets`: Datasets SDK (`tilebox.datasets`) with sync + async clients, query/data model helpers, protobuf conversion, and generated datasets-related protobuf stubs.
- `tilebox-workflows`: Workflows SDK (`tilebox.workflows`) with job/cluster/automation clients, task model + runner, observability/tracing, and generated workflows protobuf stubs.
- `tilebox-storage`: Storage SDK (`tilebox.storage`) for provider-specific payload downloads (ASF, Copernicus, Umbra, Landsat, local FS), built mostly on async internals with sync wrappers.

Design choices to keep in mind:

- Namespace package layout: multiple packages contribute modules under shared top-level namespaces like `tilebox.*`.
- Layering pattern: generated protobuf/gRPC types -> service wrappers -> data/domain classes -> user-facing clients.
- Sync + async parity: many APIs exist in both forms; sync wrappers are often derived from async implementations.
- External API communication is gRPC-first, with protobuf-generated contracts.

## Developer Tooling

Use `uv` for all local development.

### Setup

```bash
uv sync
```

### Test Commands

```bash
# All packages with coverage aggregation
./tests.sh

# Single package examples
uv run --package tilebox-datasets pytest tilebox-datasets
uv run --package tilebox-workflows pytest tilebox-workflows
uv run --package tilebox-storage pytest tilebox-storage
uv run --package tilebox-grpc pytest tilebox-grpc
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

- Python target: `>=3.10`.
- Linting/formatting is Ruff-based and fairly strict (`select = ["ALL"]`) with explicit ignores configured in root `pyproject.toml`.
- Type hints are used broadly across public APIs and internals.
- Prefer dataclasses and explicit domain objects for request/response translation.
- Service modules generally wrap generated gRPC stubs and convert to internal Pythonic types.
- Logging uses `loguru` in several packages; workflows also supports explicit logger/tracer configuration.
- Tests use `pytest`, with async coverage (`pytest-asyncio`) and property-based testing (`hypothesis`) in multiple packages.

## Protobuf And Generated Code

Generated files live under paths such as:

- `tilebox-datasets/tilebox/datasets/datasets/v1/*_pb2*.py`
- `tilebox-datasets/tilebox/datasets/tilebox/v1/*_pb2*.py`
- `tilebox-datasets/tilebox/datasets/buf/validate/*_pb2*.py`
- `tilebox-workflows/tilebox/workflows/workflows/v1/*_pb2*.py`

Regenerate protobuf code with:

```bash
uv run generate-protobuf
```

This uses `buf.gen.datasets.yaml` and `buf.gen.workflows.yaml`, then runs import-fixup logic via `tools/generate_protobuf.py`.

### Important Boundary: API Schema Source Of Truth

- Many protobuf contracts are sourced from the separate `api` repository/module (`buf.build/tilebox/api`, with optional local `../api` input in buf configs).
- Do **not** hand-edit generated `*_pb2.py`, `*_pb2.pyi`, or `*_pb2_grpc.py` files.
- If a requested change requires modifying protobuf schema/contracts, that change must be made in the `api` repo first.
- Whenever schema/proto edits are needed, ask the developer to point you to the `api` repo so those changes can be implemented there and then regenerated here.
