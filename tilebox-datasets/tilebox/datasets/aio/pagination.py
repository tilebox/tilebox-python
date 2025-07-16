import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import TypeVar

from tqdm.auto import tqdm

from tilebox.datasets.data.datapoint import QueryResultPage
from tilebox.datasets.progress import ProgressCallback, TimeIntervalProgressBar
from tilebox.datasets.query.time_interval import TimeInterval

ResultPage = TypeVar("ResultPage", bound=QueryResultPage)


async def with_progressbar(
    paginated_request: AsyncIterator[ResultPage],
    progress_description: str,
) -> AsyncIterator[ResultPage]:
    """Make a paginated request to a gRPC service endpoint while displaying the progress in a tqdm progress bar.

    We don't know the total amount of work beforehand, so the progress bar will just show the number of data points
    that have been downloaded so far.

    If we only have a single page, no progress bar is shown.

    Args:
        paginated_request: The paginated request to wrap with a progress bar
        progress_description: A short description message of the operation to display in front of the progress bar

    Yields:
        DatasetInterval: The individual pages of the response
    """
    actual_start_time = time.time()
    first_page = await anext(paginated_request)
    yield first_page

    # no more pages, return immediately to skip the progress bar
    if not first_page.next_page.starting_after or first_page.n_datapoints == 0:
        return

    with tqdm(
        desc=progress_description,
        unit="datapoints",
    ) as progress_bar:
        progress_bar.update(first_page.n_datapoints)  # one page has already been downloaded
        progress_bar.start_t = actual_start_time  # set the start time to the actual start time before the first page
        async for page in paginated_request:  # now loop over the remaining pages
            progress_bar.update(page.n_datapoints)
            yield page


async def with_time_progressbar(
    paginated_request: AsyncIterator[ResultPage],
    interval: TimeInterval,
    progress_description: str,
) -> AsyncIterator[ResultPage]:
    """Make a paginated request to a gRPC service endpoint while displaying the progress in a tqdm progress bar.

    The given interval is used to estimate a total amount of work for the progress bar. Then the event_time of the
    latest data point returned in each page is used to update the progress bar accordingly.

    If we only have a single page, no progress bar is shown.

    Args:
        paginated_request: The paginated request to wrap with a progress bar
        interval: The time interval of the request, used to estimate the total amount of work
        progress_description: A short description message of the operation to display in front of the progress bar

    Yields:
        DatasetInterval: The individual pages of the response
    """
    actual_start_time = time.time()
    first_page = await anext(paginated_request)
    yield first_page

    # no more pages, return immediately to skip the progress bar
    if not first_page.next_page.starting_after or first_page.n_datapoints == 0:
        return

    # we have more pages, so lets set up a progress bar
    actual_interval = TimeInterval(
        start=max(interval.start, first_page.min_time),
        end=min(interval.end, datetime.now(tz=timezone.utc)),
    )

    with TimeIntervalProgressBar(
        interval=actual_interval,
        description=progress_description,
        initial_time=first_page.max_time,
        actual_start_time=actual_start_time,
    ) as progress_bar:
        # provide download information for the first page
        now = time.time()
        progress_bar.set_download_info(first_page.n_datapoints, first_page.byte_size, now - actual_start_time)

        before = now
        async for page in paginated_request:  # now loop over the remaining pages
            now = time.time()
            if page.n_datapoints > 0:
                progress_bar.set_progress(page.max_time)
                progress_bar.set_download_info(page.n_datapoints, page.byte_size, now - before)
            yield page
            before = now


async def with_time_progress_callback(
    paginated_request: AsyncIterator[ResultPage],
    interval: TimeInterval,
    progress_callback: ProgressCallback,
) -> AsyncIterator[ResultPage]:
    """Make a paginated request to a gRPC service endpoint, and reporting progress percentage to a callback function.

    The given interval is used to estimate a total amount of work for the progress bar. Then the event_time of the
    latest data point returned in each page is used to calculate progress percentage.

    Args:
        paginated_request: The paginated request to wrap with a progress bar
        interval: The time interval of the request, used to estimate the total amount of work
        progress_callback: A callback function taking a float argument, which will be called with progress updates
            after each page. The argument is the total progress percentage so far, ranging from 0.0 to 1.0.

    Yields:
        DatasetInterval: The individual pages of the response
    """
    first_page = await anext(paginated_request)
    yield first_page

    # no more pages, return immediately to skip the progress bar
    if not first_page.next_page.starting_after or first_page.n_datapoints == 0:
        progress_callback(1.0)
        return

    # we have more pages, so lets set up a progress bar
    actual_interval = TimeInterval(
        start=max(interval.start, first_page.min_time),
        end=min(interval.end, datetime.now(tz=timezone.utc)),
    )

    total = (actual_interval.end - actual_interval.start).total_seconds()
    if first_page.n_datapoints > 0:
        current = (first_page.max_time - actual_interval.start).total_seconds()
        progress_callback(current / total)
    async for page in paginated_request:  # now loop over the remaining pages
        if page.n_datapoints > 0:
            current = (page.max_time - actual_interval.start).total_seconds()
            progress_callback(current / total)
        yield page

    progress_callback(1.0)
