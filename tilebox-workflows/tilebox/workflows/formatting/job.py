"""HTML formatting and ipywidgets for interactive display of Tilebox Workflow jobs."""

# some CSS helpers for our Jupyter HTML snippets - inspired by xarray's interactive display
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event, Thread
from typing import Any
from uuid import UUID

from dateutil.tz import tzlocal
from ipywidgets import HTML, HBox, IntProgress, VBox

from tilebox.workflows.data import Job, JobState


class JobWidget:
    def __init__(self, refresh_callback: Callable[[UUID], Job] | None = None) -> None:
        self.job: Job | None = None
        self.refresh_callback = refresh_callback
        self.layout: VBox | None = None
        self.widgets = []
        self.refresh_thread: Thread | None = None
        self._stop_refresh = Event()

    def __del__(self) -> None:
        self.stop()

    def _repr_mimebundle_(self, *args: Any, **kwargs: Any) -> dict[str, str] | None:
        if self.job is None:  # no job to display
            return None

        if self.layout is None:  # initialize the widget the first time we want to interactively display it
            self.widgets.append(HTML(_render_job_details_html(self.job)))
            self.widgets.append(HTML(_render_job_progress(self.job, False)))
            self.widgets.extend(
                _progress_indicator_bar(progress.label or self.job.name, progress.done, progress.total, self.job.state)
                for progress in self.job.progress
            )
            self.layout = VBox(self.widgets)
            self.refresh_thread = Thread(target=self._refresh_worker)
            self.refresh_thread.start()

        return self.layout._repr_mimebundle_(*args, **kwargs) if self.layout is not None else None

    def stop(self) -> None:
        self._stop_refresh.set()

    def _refresh_worker(self) -> None:
        """Refresh the job's progress display, intended to be run in a background thread."""

        if self.job is None or self.refresh_callback is None or self.layout is None:
            return

        last_progress: Job | None = None

        while True:
            progress = self.refresh_callback(self.job.id)
            updated = False
            if last_progress is None:  # first time, don't add the refresh time
                self.widgets[1] = HTML(_render_job_progress(progress, False))
                updated = True
            elif (
                progress.state != last_progress.state
                or progress.execution_stats.first_task_started_at != last_progress.execution_stats.first_task_started_at
            ):
                self.widgets[1] = HTML(_render_job_progress(progress, True))
                updated = True

            if last_progress is None or progress.progress != last_progress.progress:
                self.widgets[2:] = [
                    _progress_indicator_bar(
                        progress.label or self.job.name, progress.done, progress.total, self.job.state
                    )
                    for progress in progress.progress
                ]
                updated = True

            if updated:
                self.layout.children = self.widgets  # trigger a rerender of the ipywidgets

            last_progress = progress

            if last_progress.state == JobState.COMPLETED:
                self.stop()
                return  # no more refreshing needed

            refresh_wait = 5 + random.uniform(0, 2)  # noqa: S311 # wait between 5 and 7 seconds to refresh progress
            if self._stop_refresh.wait(refresh_wait):  # check if the event to stop is set, if so exit the thread
                return


@dataclass(order=True, frozen=True)
class RichDisplayJob(Job):
    _widget: JobWidget = field(compare=False, repr=False)

    def __repr__(self) -> str:
        return super().__repr__().replace(RichDisplayJob.__name__, Job.__name__)

    def _repr_mimebundle_(self, *args: Any, **kwargs: Any) -> dict[str, str] | None:
        """Called by the IPython MimeBundleFormatter for interactive display of ipywidgets.

        By overriding this and forwarding to an ipywidget, we can utilize the interactive display capabilities of
        the widget, without having to inherit from a widget as base class of the Job.
        """
        self._widget.job = self  # initialize the widget the first time we want to interactively display it
        return self._widget._repr_mimebundle_(*args, **kwargs)


_CSS = """
:root {
  --tbx-font-color0: var(
    --jp-content-font-color0,
    var(--pst-color-text-base rgba(0, 0, 0, 1))
  );
  --tbx-font-color2: var(
    --jp-content-font-color2,
    var(--pst-color-text-base, rgba(0, 0, 0, 0.54))
  );
  --tbx-border-color: var(
    --jp-border-color2,
    hsl(from var(--pst-color-on-background, white) h s calc(l - 10))
  );
}

html[theme="dark"],
html[data-theme="dark"],
body[data-theme="dark"],
body.vscode-dark {
  --tbx-font-color0: var(
    --jp-content-font-color0,
    var(--pst-color-text-base, rgba(255, 255, 255, 1))
  );
  --tbx-font-color2: var(
    --jp-content-font-color2,
    var(--pst-color-text-base, rgba(255, 255, 255, 0.54))
  );
  --tbx-border-color: var(
    --jp-border-color2,
    hsl(from var(--pst-color-on-background, #111111) h s calc(l + 10))
  );
}

.tbx-wrap {
  display: block !important;
  min-width: 300px;
  max-width: 540px;
}

.tbx-text-repr-fallback {
  /* fallback to plain text repr when CSS is not injected (untrusted notebook) */
  display: none;
}

.tbx-header {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 2px;
}

.tbx-header > .tbx-obj-type {
  padding: 3px 5px;
  line-height: 1;
  border-bottom: solid 1px var(--tbx-border-color);
}


.tbx-obj-type {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  color: var(--tbx-font-color2);
}

.tbx-detail-key {
  color: var(--tbx-font-color2);
}
.tbx-detail-mono {
  font-family: monospace;
}
.tbx-detail-value {
  color: var(--tbx-font-color0);
}
.tbx-detail-value-muted {
  color: var(--tbx-font-color2);
}

.tbx-job-state {
  border-radius: 10px;
  padding: 2px 10px;
}

.tbx-job-state-submitted {
  background-color: #f1f5f9;
  color: #0f172a;
}

.tbx-job-state-running {
  background-color: #0066ff;
  color: #f8fafc;
}

.tbx-job-state-started {
  background-color: #fd9b11;
  color: #f8fafc;
}

.tbx-job-state-completed {
  background-color: #21c45d;
  color: #f8fafc;
}

.tbx-job-state-failed {
  background-color: #f43e5d;
  color: #f8fafc;
}

.tbx-job-state-canceled {
  background-color: #94a2b3;
  color: #f8fafc;
}

.tbx-job-progress a {
  text-decoration: underline;
}

.tbx-detail-button a{
  display: flex;
  align-items: center;
  flex-direction: row;
  gap: 8px;
  font-size: 13px;
  background-color: #f43f5e;
  padding: 2px 10px;
  color: white;
}

.tbx-detail-button a svg {
  fill: white;
  stroke: white;
  stroke-width: 2px;
}

.tbx-detail-button a span {
  display: inline;
  vertical-align: middle;
  margin: 0;
  padding: 0;
  line-height: 1.8;
}

.tbx-detail-button a:hover {
  background-color: #cc4e63;
  color: white;
}
"""


def _render_job_details_html(job: Job) -> str:
    """Render a job as HTML."""
    return f"""
<style>
{_CSS}
</style>
<div class="tbx-text-repr-fallback"></div>
<div class="tbx-wrap">
    <div class="tbx-header">
        <div class="tbx-obj-type">tilebox.workflows.Job</div>
        <div class="tbx-detail-button"><a href="https://console.tilebox.com/workflows/jobs/{job.id!s}" target="_blank">{_eye_icon} <span>Tilebox Console</span></a></div>
    </div>
    <div class="tbx-job-details">
        <div><span class="tbx-detail-key tbx-detail-mono">id:</span> <span class="tbx-detail-value tbx-detail-mono">{job.id!s}</span><div>
        <div><span class="tbx-detail-key tbx-detail-mono">name:</span> <span class="tbx-detail-value">{job.name}</span><div>
        <div><span class="tbx-detail-key tbx-detail-mono">submitted_at:</span> {_render_datetime(job.submitted_at)}<div>
    </div>
</div>
"""


def _render_datetime(dt: datetime) -> str:
    local = dt.astimezone(tzlocal())
    time_part = local.strftime("%Y-%m-%d %H:%M:%S")
    tz_part = local.strftime("%z")
    tz_part = "(UTC)" if tz_part == "+0000" else f"(UTC{tz_part})"
    return f"<span class='tbx-detail-value'>{time_part}</span> <span class='tbx-detail-value-muted'>{tz_part}</span>"


def _render_job_progress(job: Job, include_refresh_time: bool) -> str:
    refresh = ""
    if include_refresh_time:
        current_time = datetime.now(tzlocal())
        refresh = f" <span class='tbx-detail-value-muted'>(refreshed at {current_time.strftime('%H:%M:%S')})</span> {_info_icon}"

    state_name = job.state.name

    no_progress = ""
    if not job.progress:
        no_progress = "<span class='tbx-detail-value-muted'>No user defined progress indicators. <a href='https://docs.tilebox.com/workflows/progress' target='_blank'>Learn more</a></span>"

    started_at = job.execution_stats.first_task_started_at

    """Render a job's progress as HTML, needs to be called after render_job_details_html since that injects the necessary CSS."""
    return f"""
<div class="tbx-wrap">
    <div class="tbx-obj-type">Progress{refresh}</div>
    <div class="tbx-job-progress">
        <div><span class="tbx-detail-key tbx-detail-mono">state:</span> <span class="tbx-job-state tbx-job-state-{state_name.lower()}">{state_name}</span><div>
        <div><span class="tbx-detail-key tbx-detail-mono">started_at:</span> {_render_datetime(started_at) if started_at else "<span class='tbx-detail-value-muted tbx-detail-mono'>None</span>"}<div>
        <div><span class="tbx-detail-key tbx-detail-mono">progress:</span> {no_progress}</div>
    </div>
</div>
    """.strip()


_BAR_COLORS = {
    "running": "#0066ff",
    "failed": "#f43e5d",
    "completed": "#21c45d",
}


def _progress_indicator_bar(label: str, done: int, total: int, state: JobState) -> HBox:
    percentage = done / total if total > 0 else 0 if done <= total else 1
    non_completed_color = (
        _BAR_COLORS["failed"] if state in (JobState.FAILED, JobState.CANCELED) else _BAR_COLORS["running"]
    )
    progress = IntProgress(
        min=0,
        max=total,
        value=done,
        description=label,
        tooltip=label,
        style={"bar_color": non_completed_color if percentage < 1 else _BAR_COLORS["completed"]},
        layout={"width": "400px"},
    )
    label_html = (
        f"<span class='tbx-detail-mono'><span class='tbx-detail-value'>{percentage:.0%}</span> "
        f"<span class='tbx-detail-value-muted'>({done} / {total})</span></span>"
    )
    label = HTML(label_html)
    return HBox([progress, label])


_eye_icon = """
<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="16px"
  height="16px" viewBox="0 0 72 72" enable-background="new 0 0 72 72" xml:space="preserve">
<g>
	<g>
		<path d="M36.001,63.75C24.233,63.75,2.5,54.883,2.5,42.25c0-12.634,21.733-21.5,33.501-21.5c11.766,0,33.5,8.866,33.5,21.5
			C69.501,54.883,47.767,63.75,36.001,63.75z M36.001,24.75C24.886,24.75,6.5,32.929,6.5,42.25c0,9.32,18.387,17.5,29.501,17.5
			c11.113,0,29.5-8.18,29.5-17.5C65.501,32.929,47.114,24.75,36.001,24.75z"/>
	</g>
	<g>
		<path d="M36.001,52.917c-5.791,0-10.501-4.709-10.501-10.5c0-5.79,4.711-10.5,10.501-10.5c5.789,0,10.5,4.71,10.5,10.5
			C46.501,48.208,41.79,52.917,36.001,52.917z M36.001,33.917c-4.688,0-8.501,3.814-8.501,8.5c0,4.688,3.813,8.5,8.501,8.5
			c4.686,0,8.5-3.813,8.5-8.5C44.501,37.731,40.687,33.917,36.001,33.917z"/>
	</g>
	<g>
		<path d="M32.073,39.809c-0.242,0-0.484-0.088-0.677-0.264c-0.406-0.375-0.433-1.008-0.059-1.414
			c0.2-0.217,0.415-0.422,0.644-0.609c0.428-0.352,1.058-0.291,1.408,0.137c0.352,0.426,0.29,1.057-0.136,1.408
			c-0.158,0.129-0.307,0.27-0.444,0.418C32.612,39.7,32.342,39.809,32.073,39.809z"/>
	</g>
	<g>
		<path d="M36.001,48.75c-3.494,0-6.335-2.842-6.335-6.334c0-0.553,0.448-1,1-1c0.553,0,1,0.447,1,1
			c0,2.391,1.945,4.334,4.335,4.334c0.553,0,1,0.447,1,1S36.554,48.75,36.001,48.75z"/>
	</g>
	<g>
		<path d="M35.876,18.25c-1.105,0-2-0.896-2-2v-6c0-1.104,0.895-2,2-2c1.104,0,2,0.896,2,2v6
			C37.876,17.354,36.979,18.25,35.876,18.25z"/>
	</g>
	<g>
		<path d="M24.353,18.93c-0.732,0-1.437-0.402-1.788-1.101l-1.852-3.68c-0.497-0.987-0.1-2.189,0.888-2.686
			c0.985-0.498,2.188-0.101,2.686,0.887l1.852,3.68c0.496,0.987,0.099,2.189-0.888,2.686C24.962,18.861,24.655,18.93,24.353,18.93z"
			/>
	</g>
	<g>
		<path d="M12.684,23.567c-0.548,0-1.094-0.224-1.488-0.663l-2.6-2.894c-0.738-0.822-0.671-2.087,0.151-2.824
			c0.82-0.74,2.085-0.672,2.824,0.15l2.6,2.894c0.738,0.822,0.67,2.087-0.151,2.824C13.638,23.398,13.16,23.567,12.684,23.567z"/>
	</g>
	<g>
		<path d="M46.581,18.93c-0.303,0-0.609-0.068-0.898-0.214c-0.986-0.496-1.383-1.698-0.887-2.686l1.852-3.68
			c0.494-0.985,1.695-1.386,2.686-0.887c0.986,0.496,1.385,1.698,0.887,2.686l-1.852,3.68C48.019,18.527,47.313,18.93,46.581,18.93z
			"/>
	</g>
	<g>
		<path d="M58.249,23.567c-0.475,0-0.953-0.169-1.336-0.513c-0.82-0.737-0.889-2.002-0.15-2.824l2.6-2.894
			c0.738-0.82,2.002-0.89,2.824-0.15c0.822,0.737,0.889,2.002,0.15,2.824l-2.6,2.894C59.343,23.344,58.798,23.567,58.249,23.567z"/>
	</g>
</g>
</svg>
""".strip()

_info_icon = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="24px" height="24px">
  <title>The progress information below is a live update and will refresh automatically. These live updates are not reflected in the underlying job object variables.</title>
  <path d="M 32 10 C 19.85 10 10 19.85 10 32 C 10 44.15 19.85 54 32 54 C 44.15 54 54 44.15 54 32 C 54 19.85 44.15 10 32 10 z M 32 14 C 41.941 14 50 22.059 50 32 C 50 41.941 41.941 50 32 50 C 22.059 50 14 41.941 14 32 C 14 22.059 22.059 14 32 14 z M 32 21 C 30.343 21 29 22.343 29 24 C 29 25.657 30.343 27 32 27 C 33.657 27 35 25.657 35 24 C 35 22.343 33.657 21 32 21 z M 32 30 C 30.895 30 30 30.896 30 32 L 30 42 C 30 43.104 30.895 44 32 44 C 33.105 44 34 43.104 34 42 L 34 32 C 34 30.896 33.105 30 32 30 z"/>
</svg>
""".strip()
