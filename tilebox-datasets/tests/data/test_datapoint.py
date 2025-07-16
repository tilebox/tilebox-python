from hypothesis import given

from tests.data.datapoint import anys, ingest_datapoints_responses, query_result_pages, repeated_anys
from tilebox.datasets.data.datapoint import AnyMessage, IngestResponse, QueryResultPage, RepeatedAny


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
