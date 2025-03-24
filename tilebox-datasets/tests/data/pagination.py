from hypothesis.strategies import (
    DrawFn,
    booleans,
    composite,
    integers,
    uuids,
)

from tilebox.datasets.data.pagination import Pagination


@composite
def paginations(draw: DrawFn, empty: bool | None = None) -> Pagination:
    """A hypothesis strategy for generating random paginations"""
    if empty is None:
        empty = draw(booleans())

    if empty:
        return Pagination()
    return Pagination(limit=draw(integers(min_value=100, max_value=1000)), starting_after=draw(uuids(version=4)))
