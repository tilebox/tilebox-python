import sys
import time
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from hypothesis import given
from IPython.core.formatters import DisplayFormatter

from tests.tasks_data import jobs
from tilebox.workflows.data import Job
from tilebox.workflows.formatting.job import JobWidget, RichDisplayJob, _render_datetime


@given(jobs())
def test_plain_text_display_without_notebook_extra(job: Job) -> None:
    rich_job = RichDisplayJob(**vars(job), _widget=JobWidget())
    with patch.dict(sys.modules, {"ipywidgets": None}):
        data, _ = DisplayFormatter().format(rich_job)
    assert data == {"text/plain": repr(rich_job)}
    assert rich_job._widget.refresh_thread is None


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset is unavailable on Windows")
@pytest.mark.parametrize(
    ("zone", "instant", "expected_time", "expected_offset"),
    [
        ("UTC", "2026-03-29T01:30:00+00:00", "2026-03-29 01:30:00", "(UTC)"),
        ("Europe/Vienna", "2026-03-29T00:30:00+00:00", "2026-03-29 01:30:00", "(UTC+0100)"),
        ("Europe/Vienna", "2026-03-29T01:30:00+00:00", "2026-03-29 03:30:00", "(UTC+0200)"),
    ],
)
def test_render_datetime_local_timezone(
    monkeypatch: pytest.MonkeyPatch, zone: str, instant: str, expected_time: str, expected_offset: str
) -> None:
    try:
        with monkeypatch.context() as context:
            context.setenv("TZ", zone)
            time.tzset()
            rendered = _render_datetime(datetime.fromisoformat(instant).astimezone(UTC))
            assert rendered == (
                f"<span class='tbx-detail-value'>{expected_time}</span> "
                f"<span class='tbx-detail-value-muted'>{expected_offset}</span>"
            )
    finally:
        time.tzset()
