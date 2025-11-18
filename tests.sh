#!/bin/sh
# Helper script to run tests on all python packages in the monorepo
# Needed because you can't run pytest on multiple packages at once

# finds also packages in the `.venv` subdirectory, so we need to filter them out => grep tilebox
packages=$(find . -name pyproject.toml -exec dirname {} \; | grep tilebox | cut -d '/' -f 2 | sort)

for package in $packages; do
    cd "$package" || exit 1 # cd into the package directory

    echo "Running tests of $package"
    module=tilebox
    if [ -d _tilebox ]; then
        module=_tilebox
    fi

    PYTHON_VERSION=$(uv run python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)

    if [ "$PYTHON_VERSION" = "3.10" ]; then
        # ignore: FutureWarning: You are using a Python version (3.10.11) which Google will stop supporting in new releases of google.api_core once it reaches its end of life (2026-10-04).
        uv run --all-packages pytest -Wall -Werror -W "ignore::FutureWarning" --cov=$module --cov-branch -v --junitxml=test-report.xml . || exit 1
    else
        uv run --all-packages pytest -Wall -Werror --cov=$module --cov-branch -v --junitxml=test-report.xml . || exit 1
    fi

    cd .. || exit 1 # cd back to the root of the monorepo
done

uv run coverage combine */.coverage
uv run coverage xml

uv run junitparser merge */test-report.xml test-report.xml
