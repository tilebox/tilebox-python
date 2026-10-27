#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
generated=$(mktemp -d)
trap 'rm -rf "$generated"' EXIT HUP INT TERM

buf generate --template buf.gen.yaml --output "$generated"
# Strip upstream trailing whitespace, including docstrings, before replacing files.
uv run --no-sync ruff check --isolated --select W291 --fix --unsafe-fixes --ignore-noqa "$generated"

for mapping in \
    datasets/v1:tilebox-datasets/tilebox/datasets/v1 \
    datasets/stac:tilebox-datasets/tilebox/datasets/stac \
    tilebox/v1:tilebox-core/_tilebox/proto/tilebox/v1 \
    workflows/v1:tilebox-workflows/tilebox/workflows/v1 \
    opentelemetry:tilebox-workflows/tilebox/workflows/_otel/opentelemetry
do
    source=${mapping%%:*}
    destination=${mapping#*:}
    rm -rf "$destination"
    mv "$generated/$source" "$destination"
done
