from hypothesis import given

from tests.data.datapoint import anys, datapoint_intervals, datapoint_pages, datapoints, repeated_anys
from tilebox.datasets.data.datapoint import Any, Datapoint, DatapointInterval, DatapointPage, RepeatedAny


@given(datapoint_intervals())
def test_datapoint_intervals_to_message_and_back(interval: DatapointInterval) -> None:
    assert DatapointInterval.from_message(interval.to_message()) == interval


@given(anys())
def test_anys_to_message_and_back(any_: Any) -> None:
    assert Any.from_message(any_.to_message()) == any_


@given(repeated_anys())
def test_repeated_anys_to_message_and_back(repeated_any: RepeatedAny) -> None:
    assert RepeatedAny.from_message(repeated_any.to_message()) == repeated_any


@given(datapoints())
def test_datapoints_to_message_and_back(datapoint: Datapoint) -> None:
    assert Datapoint.from_message(datapoint.to_message()) == datapoint


@given(datapoint_pages())
def test_datapoint_pages_to_message_and_back(page: DatapointPage) -> None:
    assert DatapointPage.from_message(page.to_message()) == page
