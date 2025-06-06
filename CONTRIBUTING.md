# Contributing to Tilebox Python

Welcome! We're excited that you're interested in contributing to Tilebox Python. This document provides guidelines and information to help you get started.

## Module and package structure

This repository contains multiple python packages. We use python [namespace packages](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/) to
organize our code into multiple packages that then share the common `tilebox` python module name.

## Required tooling

Before starting to work on this repository, make sure you have uv installed. [Install instructions](https://docs.astral.sh/uv/getting-started/installation/).

## Workspace setup

This repository is set up as a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/).

This means it contains multiple packages, which all share the same virtualenv, and may have interdependencies between
them.

## Useful commands for development

### Initial setup

```bash
uv sync
```

### Running tests

```bash
./tests.sh  # helper script for running with coverage

# testing a single package
uv run --package tilebox-datasets pytest tilebox-datasets
```

### Running code analysis

```bash
# formatting and linting:
uv run ruff format . && uv run ruff check --fix .

# type checking:
uv run pyright .
```

### Adding dependencies to one of the packages

```bash
uv add --package tilebox-datasets "numpy>=2"
```

### Used code quality tools

- [ruff](https://github.com/astral-sh/ruff) for linting and formatting
- [pyright](https://github.com/microsoft/pyright) for type checking
- [pre-commit](https://pre-commit.com/) for running all of the above automatically on each git commit

## Protobuf usage

We use [protobuf](https://protobuf.dev/) for defining our API contracts. The protobuf files are generated from the messages
defined in the [Tilebox Go repository](https://github.com/tilebox/tilebox-go/tree/main/apis).

### Updating protobuf files

```bash
uv run copy-protobuf
```

## Releasing and deploying a new version

There is a Github CI workflow set up for building the packages and pushing them to the internal `pypi`.
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
