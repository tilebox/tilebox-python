"""Utilities for working with xarray datapoints returned by dataset queries."""

from collections.abc import Iterator

import xarray as xr


def iter_datapoints(data: xr.Dataset, *, dimension: str = "time") -> Iterator[xr.Dataset]:
    """Yield scalar datapoints from an xarray query result."""
    if dimension not in data.sizes:
        raise ValueError(f"datapoint dimension {dimension!r} is not present in the dataset")
    for index in range(data.sizes[dimension]):
        yield data.isel({dimension: index})
