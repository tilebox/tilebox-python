# Tilebox Core

Shared types and client infrastructure for the Tilebox Python SDKs.

Public imports are `tilebox.query` for `TimeInterval`, `IDInterval`, and `Pagination`,
and `tilebox.errors` for SDK exceptions. The `_tilebox` namespace contains private
connections, generated messages, conversions, retries, pagination, and test utilities.

Core does not depend on datasets or its scientific libraries. Parsing ordinary Python
datetimes requires no optional libraries. Strings and scientific datetime values use
pandas when parsed; xarray inputs also require xarray. Install pandas explicitly for
these parsing conveniences in workflows-only environments. Datasets already installs
these libraries.

Run tests in the workspace with `uv sync --all-packages` followed by
`uv run --no-sync pytest tilebox-core`. Transport tests use generated datasets clients.
