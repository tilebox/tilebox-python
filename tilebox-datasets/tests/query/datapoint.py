from hypothesis.strategies import DrawFn, booleans, composite, just, one_of, uuids

from tilebox.datasets.query.id_interval import IDInterval, IDIntervalLike


@composite
def id_intervals(draw: DrawFn) -> IDInterval:
    """A hypothesis strategy for generating random id intervals"""
    start = draw(uuids(version=4))
    end = draw(uuids(version=4))
    start, end = min(start, end), max(start, end)  # make sure start is before end

    start_exclusive = draw(booleans())
    end_inclusive = draw(booleans())

    return IDInterval(start, end, start_exclusive, end_inclusive)


@composite
def id_intervals_like(draw: DrawFn) -> IDIntervalLike:
    """A hypothesis strategy for generating random id intervals"""
    interval = draw(id_intervals())
    return draw(
        one_of(
            just(interval),
            just((str(interval.start_id), str(interval.end_id))),
            just((interval.start_id, interval.end_id)),
        )
    )
