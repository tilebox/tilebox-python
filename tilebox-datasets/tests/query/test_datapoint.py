from hypothesis import given
from tests.query.datapoint import id_intervals, id_intervals_like

from tilebox.datasets.query.id_interval import IDInterval, IDIntervalLike


@given(id_intervals())
def test_id_intervals_to_message_and_back(interval: IDInterval) -> None:
    assert IDInterval.from_message(interval.to_message()) == interval


@given(id_intervals_like())
def test_parse_id_interval_from_tuple(interval: IDIntervalLike) -> None:
    parsed = IDInterval.parse(interval)

    if isinstance(interval, IDInterval):
        assert parsed == interval, f"Failed parsing interval from {interval}"
        assert parsed.start_exclusive == interval.start_exclusive
        assert parsed.end_inclusive == interval.end_inclusive
    else:
        assert not parsed.start_exclusive
        assert parsed.end_inclusive
