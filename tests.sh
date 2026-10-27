#!/bin/sh
# Helper script to run tests on all python packages in the monorepo
# Needed because you can't run pytest on multiple packages at once

# Keep generated SDK clients available to the RPC tests without a runtime dependency cycle.
packages="tilebox-datasets tilebox-core tilebox-storage tilebox-workflows"

for package in $packages; do
    cd "$package" || exit 1 # cd into the package directory

    echo "Running tests of $package"
    set -- --cov=tilebox
    if [ -d _tilebox ]; then
        set -- "$@" --cov=_tilebox
    fi

    uv run --no-sync pytest -Wall -Werror "$@" --cov-branch -v --junitxml=test-report.xml . || exit 1

    cd .. || exit 1 # cd back to the root of the monorepo
done

set --
for package in $packages; do
    set -- "$@" "$package/.coverage"
done
uv run --no-sync coverage combine "$@"
uv run --no-sync coverage xml

set --
for package in $packages; do
    set -- "$@" "$package/test-report.xml"
done
uv run --no-sync junitparser merge "$@" test-report.xml
