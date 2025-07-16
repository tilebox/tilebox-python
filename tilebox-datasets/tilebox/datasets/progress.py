from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Any

from tqdm.auto import tqdm

from tilebox.datasets.query.time_interval import TimeInterval

ProgressCallback = Callable[[float], Any]


class TimeIntervalProgressBar:
    def __init__(
        self,
        interval: TimeInterval,
        description: str | None,
        initial_time: datetime | None = None,
        actual_start_time: float | None = None,
    ) -> None:
        """
        Create a progress bar which shows the progress of a time interval.

        Wraps tqdm to make it easier to work with time based progress bars.
        Intended to be used as a context manager.

        Example:
        >>> with TimeIntervalProgressBar(interval, "Fetching data") as progress_bar:
        >>>     while data := fetch_data(...):
        >>>         progress_bar.set_progress(data[-1].time)

        Args:
            interval: time interval to show the progress of
            description: description to show in the progress bar
            initial_time: initial time to show the progress of, if None the progress bar starts at 0
            actual_start_time: The time.time() measurement when the actual work started, in case this was before the
                progress bar was created. This is used to make the remaining time estimate more accurate.
        """
        self._interval = interval
        self._description = description or ""
        self._initial_time = initial_time
        self._actual_start_time = actual_start_time
        self._total_data_points = 0

    def __enter__(self) -> "TimeIntervalProgressBar":
        self._progress_bar = tqdm(
            bar_format="{l_bar}{bar}[{elapsed}<{remaining}{postfix}]",
            total=self._calc_progress_seconds(self._interval.end),
            initial=self._calc_progress_seconds(self._initial_time) if self._initial_time is not None else 0,
            desc=self._description,
        )
        if self._actual_start_time is not None:
            self._progress_bar.start_t = self._actual_start_time
        self._progress_bar.set_postfix_str("test")
        return self

    def _calc_progress_seconds(self, time: datetime) -> int:
        """
        Convert the given progress time to the corresponding number of seconds since the start of the interval
        """
        return int((time - self._interval.start).total_seconds())

    def set_progress(self, time: datetime) -> None:
        """Set the progress of the progress bar to the given time"""
        done = min(self._calc_progress_seconds(time), self._progress_bar.total)
        self._progress_bar.update(done - self._progress_bar.n)

    def set_download_info(self, datapoints: int, byte_size: int, download_time: float) -> None:
        """Set the download info of the progress bar to the given values"""
        self._total_data_points += datapoints
        mb_per_s = byte_size / 1024 / 1024 / download_time
        self._progress_bar.set_postfix_str(f"{self._total_data_points} datapoints, {mb_per_s:.2f} MB/s")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if traceback is None:
                self._progress_bar.update(self._progress_bar.total - self._progress_bar.n)  # set to 100%

            self._progress_bar.close()  # mark as completed or failed
        except AttributeError:
            pass
