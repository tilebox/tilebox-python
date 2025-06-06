# Tilebox Python Packages

Mono-repo containing various Tilebox python packages.

## Module and package structure

We use python [namespace packages](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/) to
organize our code into multiple packages that then share a common python module name.

Currently we use the following top level module names:

```
import tilebox  # public API
import _tilebox  # private, internal modules
```

There is some inter-dependency across packages in this repository. A quick overview of how they are connected
provides this diagram:

![Package Dependency Overview](.docs/packages.svg)

## Required tooling

Before starting to work on this repository, make sure you have poetry installed. [Install instructions](https://python-poetry.org/docs/#installation).

Additionally the `poetry-dynamic-versioning` plugin is required, if not yet installed it can be installed with this command:

```bash
poetry self add "poetry-dynamic-versioning[plugin]"
```

## Development environment

For each package (which are a subdirectory of this repository) there is a separate `pyproject.toml` file.

But for convenience there is also one `pyproject.toml` file in the root directory, that contains all subpackages as
editable path dependency. That way the virtualenv created by poetry contains all packages and can be used for
development.

### Initial setup

```bash
poetry install
pre-commit install
```

### Running tests

```bash
# for all packages, run from repository root
./tests.sh  # helper script for running with coverage

# testing a single package
cd tilebox-datasets
pytest .
```

### Running code analysis

```bash
# run all checks at once for all packages
pre-commit run --all-files

# alternatively, run a singler code analysis tool for all packages from repository root
ruff format .
pyright .
ruff check .

# or for just a single package, run from package root
cd tilebox-datasets
ruff format .
pyright .
ruff check .
```

### Used code quality tools

- [ruff](https://github.com/astral-sh/ruff) for linting and formatting
- [pyright](https://github.com/microsoft/pyright) for type checking
- [pre-commit](https://pre-commit.com/) for running all of the above automatically on each git commit

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
