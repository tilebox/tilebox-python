import string
from datetime import timezone

from hypothesis.strategies import DrawFn, composite, integers, just, none, text, uuids

from tests.data.time_interval import time_intervals
from tilebox.datasets.data.collection import Collection, CollectionInfo
from tilebox.datasets.data.time_interval import _EMPTY_TIME_INTERVAL


@composite
def collection_names(draw: DrawFn) -> str:
    """A hypothesis strategy for generating random collection names"""
    # the text() strategy gets a bit crazy with utf codepoints, so lets restrict it a bit
    return draw(text(alphabet=string.ascii_letters + string.digits + "-_", min_size=1, max_size=100))


@composite
def collections(draw: DrawFn) -> Collection:
    """A hypothesis strategy for generating random collections"""
    return Collection(str(draw(uuids(version=4))), draw(collection_names()))


uint64s = integers(min_value=0, max_value=2**64 - 1)


@composite
def collection_infos(draw: DrawFn) -> CollectionInfo:
    """A hypothesis strategy for generating random collection infos"""
    collection = draw(collections())
    interval = draw(none() | just(_EMPTY_TIME_INTERVAL) | time_intervals(tzinfo=timezone.utc))
    count = draw(none() | uint64s)
    return CollectionInfo(collection, interval, count)
