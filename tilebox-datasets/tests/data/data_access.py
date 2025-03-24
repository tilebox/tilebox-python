from hypothesis.strategies import (
    DrawFn,
    composite,
    one_of,
)

from tests.data.datapoint import datapoint_intervals
from tests.data.time_interval import time_intervals
from tilebox.datasets.data.data_access import QueryFilters


@composite
def query_filters(draw: DrawFn) -> QueryFilters:
    """A hypothesis strategy for generating random query filters"""
    interval = draw(one_of(time_intervals(), datapoint_intervals()))
    return QueryFilters(interval)
