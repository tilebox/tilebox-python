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
    uv run --package "$package" pytest -Wall -Werror --cov=$module --cov-branch -v --junitxml=test-report.xml . || exit 1

    cd .. || exit 1 # cd back to the root of the monorepo
done

uv run coverage combine */.coverage
uv run coverage xml

uv run junitparser merge */test-report.xml test-report.xml
