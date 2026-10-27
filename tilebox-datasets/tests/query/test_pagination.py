from collections.abc import AsyncIterator
from functools import partial
from io import StringIO
from unittest.mock import patch
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis.strategies import integers, lists
from tests.query.pagination import paginations
from tqdm import tqdm

from tilebox.datasets.aio.pagination import with_progressbar as async_with_progressbar
from tilebox.datasets.data.datapoint import QueryResultPage, RepeatedAny
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.sync.pagination import with_progressbar


@given(paginations())
def test_pages_to_message_and_back(page: Pagination) -> None:
    assert Pagination.from_message(page.to_message()) == page


@pytest.mark.asyncio
@given(page_sizes=lists(integers(min_value=1, max_value=100), min_size=2, max_size=5))
async def test_progress_counts_actual_datapoints_in_sync_and_async_pages(page_sizes: list[int]) -> None:
    pages = [
        QueryResultPage(
            RepeatedAny("", [b""] * size),
            Pagination(starting_after=UUID(int=index + 1) if index < len(page_sizes) - 1 else None),
            byte_size=0,
        )
        for index, size in enumerate(page_sizes)
    ]

    async def async_pages() -> AsyncIterator[QueryResultPage]:
        for page in pages:
            yield page

    for module in ("sync", "aio"):
        output = StringIO()
        with patch(
            f"tilebox.datasets.{module}.pagination.tqdm",
            partial(tqdm, file=output, bar_format="{n}", mininterval=0),
        ):
            if module == "sync":
                result = list(with_progressbar(iter(pages), "query"))
            else:
                result = [page async for page in async_with_progressbar(async_pages(), "query")]
        assert result == pages
        assert int(output.getvalue().strip().rsplit("\r", maxsplit=1)[-1]) == sum(page_sizes)
