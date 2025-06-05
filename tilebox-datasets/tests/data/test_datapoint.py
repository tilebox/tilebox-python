from hypothesis import given

from tests.data.datapoint import (
    anys,
    datapoint_intervals,
    datapoint_intervals_like,
    ingest_datapoints_responses,
    query_result_pages,
    repeated_anys,
)
from tilebox.datasets.data.datapoint import (
    AnyMessage,
    DatapointInterval,
    DatapointIntervalLike,
    IngestResponse,
    QueryResultPage,
    RepeatedAny,
)


@given(datapoint_intervals())
def test_datapoint_intervals_to_message_and_back(interval: DatapointInterval) -> None:
    assert DatapointInterval.from_message(interval.to_message()) == interval


@given(datapoint_intervals_like())
def test_parse_datapoint_interval_from_tuple(interval: DatapointIntervalLike) -> None:
    parsed = DatapointInterval.parse(interval)

    if isinstance(interval, DatapointInterval):
        assert parsed == interval, f"Failed parsing interval from {interval}"
        assert parsed.start_exclusive == interval.start_exclusive
        assert parsed.end_inclusive == interval.end_inclusive
    else:
        assert not parsed.start_exclusive
        assert parsed.end_inclusive


@given(anys())
def test_anys_to_message_and_back(any_: AnyMessage) -> None:
    assert AnyMessage.from_message(any_.to_message()) == any_


@given(repeated_anys())
def test_repeated_anys_to_message_and_back(repeated_any: RepeatedAny) -> None:
    assert RepeatedAny.from_message(repeated_any.to_message()) == repeated_any


@given(query_result_pages())
def test_query_result_pages_to_message_and_back(page: QueryResultPage) -> None:
    assert QueryResultPage.from_message(page.to_message()) == page


@given(ingest_datapoints_responses())
def test_ingest_datapoints_responses_to_message_and_back(response: IngestResponse) -> None:
    assert IngestResponse.from_message(response.to_message()) == response
