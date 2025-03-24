from hypothesis import given

from tests.data.data_access import query_filters
from tilebox.datasets.data.data_access import QueryFilters


@given(query_filters())
def test_query_filters_to_message_and_back(q: QueryFilters) -> None:
    assert QueryFilters.from_message(q.to_message()) == q
