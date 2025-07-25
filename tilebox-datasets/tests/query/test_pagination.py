from hypothesis import given
from tests.query.pagination import paginations

from tilebox.datasets.query.pagination import Pagination


@given(paginations())
def test_pages_to_message_and_back(page: Pagination) -> None:
    assert Pagination.from_message(page.to_message()) == page
