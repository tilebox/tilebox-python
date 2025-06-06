#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 <package_dir>"
    exit 1
}

PACKAGE_DIR=""

if [ $# -gt 1 ]; then
    usage
elif [ $# -eq 1 ]; then
    PACKAGE_DIR=$1
elif [ $# -lt 1 ]; then
    echo "No package directory provided"
    usage
fi

# Helper script to run build a package of the monorepo, and move the built artifacts to the dist folder in the repo root

rm -rf dist && mkdir dist

cd "$PACKAGE_DIR" || exit 1 # cd into the package directory

echo "Building $PACKAGE_DIR"
poetry build || exit 1
mv dist/* ../dist/

cd .. || exit 1 # cd back to the root of the monorepo

poetry run wheel-doctor remove-path-dependencies dist/*

for wheel in dist/*; do
    poetry run wheel-doctor show-dependencies "$wheel"
done
