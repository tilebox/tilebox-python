# Contributing to Tilebox Python

Welcome! We're excited that you're interested in contributing to Tilebox Python. This document provides guidelines and information to help you get started.

## Module and package structure

This repository contains multiple python packages. We use python [namespace packages](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/) to
organize our code into multiple packages that then share the common `tilebox` python module name.

`tilebox-core` owns the public `tilebox.query` and `tilebox.errors` APIs and the private
`_tilebox` infrastructure namespace. Datasets, workflows, and storage depend on core;
scientific dependencies stay in datasets. Core and workflows have no runtime dependency
on datasets. Their cross-SDK tests run in the all-packages workspace environment.
`tilebox-grpc` is a dependency-only compatibility package retained for the 0.68 release.

## Required tooling

Before starting to work on this repository, make sure you have uv installed. [Install instructions](https://docs.astral.sh/uv/getting-started/installation/).

## Workspace setup

This repository is set up as a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/).

This means it contains multiple packages, which all share the same virtualenv, and may have interdependencies between
them.

## Useful commands for development

### Initial setup

```bash
uv sync --all-packages
```

### Running tests

```bash
./tests.sh  # helper script for running with coverage

# testing a single package
uv run --package tilebox-datasets pytest tilebox-datasets
uv run --no-sync pytest tilebox-core
```

### Running code analysis

```bash
# formatting and linting:
uv run ruff format . && uv run ruff check --fix .

# type checking:
uv run ty check
```

### Adding dependencies to one of the packages

```bash
uv add --package tilebox-datasets "numpy>=2"
```

### Used code quality tools

- [ruff](https://github.com/astral-sh/ruff) for linting and formatting
- [ty](github.com/astral-sh/ty) for type checking
- [prek](https://prek.j178.dev/) for running all of the above automatically on each git commit

## Protobuf usage

We use [protobuf](https://protobuf.dev/) for defining our API contracts. The protobuf files are generated from the messages
defined in [Tilebox API](https://buf.build/tilebox/api). `buf.gen.yaml` defines schema inputs, import mappings, and pinned native Python plugins.

### Updating protobuf files

```bash
./tools/generate-protobuf.sh
```

The script generates into a temporary directory, strips trailing whitespace with Ruff, and replaces the generated
modules in each package. API types live in `tilebox.datasets.v1`, `tilebox.datasets.stac.v1`, and `tilebox.workflows.v1`;
shared generated types live in `_tilebox.proto.tilebox.v1`. Workflows bundles its API telemetry types privately under
`tilebox.workflows._otel`. The OpenTelemetry SDK and exporters continue to use their own generated types.

## Releasing and deploying a new version

There is a Github CI workflow set up for building the packages and pushing them to the internal `pypi`.
Sibling-package dependencies require at least version 0.68.0 for the Connect migration.
Raise these minimums only when a package needs a newer sibling. Make core available before its dependents,
and datasets before storage. The release workflows run independently; do not announce installation availability
until all packages have published successfully.
Before the first core release, configure PyPI trusted publishing for `tilebox-core` using this repository's
`publish_tilebox_core.yml` workflow. The compatibility `tilebox-grpc` wheel must contain no Python modules.
All that is needed is to create a github release for a given tag. This can be done in the github web UI or on the
command line.

For example, to release a version `0.1.0` via the CLI the following commands could be used:
(this uses [parse-changelog](https://github.com/taiki-e/parse-changelog) for release notes)

```bash
git tag "v0.1.0" -m "Tilebox Python Release v0.1.0"
git push -u origin v0.1.0
gh release create v0.1.0 --notes $(parse-changelog CHANGELOG.md)
# wait a bit until CI pipeline is done and voila!
```
