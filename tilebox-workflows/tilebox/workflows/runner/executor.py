import json
import logging
from base64 import b64encode
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol
from warnings import warn

from opentelemetry.trace.status import StatusCode

from tilebox.workflows.cache import JobCache
from tilebox.workflows.data import ComputedTask, FailedTask, ProgressIndicator, Task
from tilebox.workflows.observability.logging import StructuredLogger
from tilebox.workflows.observability.tracing import NoopWorkflowTracer, WorkflowTracer, start_job_span
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.runtime import RunnerRuntime
from tilebox.workflows.task import ExecutionContext as ExecutionContextBase
from tilebox.workflows.task import FutureTask, ProgressUpdate, RunnerContext, merge_future_tasks_to_submissions
from tilebox.workflows.task import Task as TaskInstance

_MAX_TASK_PROGRESS_INDICATORS = 1000


class LeaseManager(Protocol):
    @contextmanager
    def lease_extension(self, task: Task) -> Iterator[None]: ...


class NoopLeaseManager:
    @contextmanager
    def lease_extension(self, task: Task) -> Iterator[None]:  # noqa: ARG002
        yield


class ApiLeaseManager:
    def __init__(self, lease_renewer: object) -> None:
        self._lease_renewer = lease_renewer

    @contextmanager
    def lease_extension(self, task: Task) -> Iterator[None]:
        if task.lease is None:
            raise ValueError(f"Task {task.id} has no lease associated with it.")

        with self._lease_renewer.lease_extension(task.id, task.lease):  # ty: ignore[unresolved-attribute]
            yield


class TaskExecutor:
    def __init__(
        self,
        runner: Runner,
        runtime: RunnerRuntime,
        *,
        fallback_cluster: str | None,
        lease_manager: LeaseManager,
    ) -> None:
        self.runner = runner
        self.runtime = runtime
        self.fallback_cluster = fallback_cluster
        self.lease_manager = lease_manager

    def execute(
        self,
        task: Task,
        task_execution_context: Callable[[Task, "ExecutionContext"], AbstractContextManager[None]] | None = None,
    ) -> ComputedTask | FailedTask:
        if task.job is None:
            raise ValueError(f"Task {task.id} has no job associated with it.")

        context = ExecutionContext(self.runtime, task, self.runtime.cache.group(str(task.job.id)))
        task_repr = str(task.id)
        if task_execution_context is None:
            task_execution_context = _null_task_execution_context

        with (
            self.lease_manager.lease_extension(task),
            start_job_span(self.runtime.tracer, task.job, f"task/{task.id}") as span,
        ):
            try:
                try:
                    task_class = self.runner.tasks_by_identifier[task.identifier]
                    task_repr = task_class.__name__
                except KeyError:
                    raise ValueError(f"Task {task.id} has unknown task identifier {task.identifier}") from None

                span.update_name(f"task/{task_repr}")
                span.set_attribute("task_id", str(task.id))
                span.set_attribute("identifier.name", task.identifier.name)
                span.set_attribute("identifier.version", task.identifier.version)

                try:
                    task_instance = task_class._deserialize(task.input, self.runtime.context)  # noqa: SLF001
                except json.JSONDecodeError:
                    raise ValueError(f"Failed to deserialize input for task execution {task.id}") from None

                task_input_span_attr = ""
                if task.input is not None:
                    try:
                        task_input_span_attr = task.input.decode("utf-8")
                    except UnicodeDecodeError:
                        task_input_span_attr = b64encode(task.input).decode("ascii")
                span.set_attribute("input", task_input_span_attr)

                with task_execution_context(task, context):
                    _execute(task_instance, context)

                fallback_cluster = self.fallback_cluster
                if fallback_cluster is None and self.runtime.cluster is not None:
                    fallback_cluster = self.runtime.cluster.slug
                fallback_cluster = fallback_cluster or ""
                return ComputedTask(
                    id=task.id,
                    display=task.display,
                    sub_tasks=merge_future_tasks_to_submissions(
                        context._sub_tasks,  # noqa: SLF001
                        fallback_cluster,
                    ),
                    progress_updates=_finalize_mutable_progress_trackers(context._progress_indicators),  # noqa: SLF001
                )
            except Exception as error:  # noqa: BLE001
                span.record_exception(error)
                span.set_status(StatusCode.ERROR, "Task failed with exception")
                return FailedTask.from_task_error(
                    task,
                    error,
                    was_workflow_error=True,
                    progress_updates=_finalize_mutable_progress_trackers(context._progress_indicators),  # noqa: SLF001
                )


class ExecutionContext(ExecutionContextBase):
    def __init__(self, runtime: RunnerRuntime, task: Task, job_cache: JobCache) -> None:
        self._runner = runtime
        self.current_task = task
        self.job_cache = job_cache
        self._sub_tasks: list[FutureTask] = []
        self._progress_indicators: dict[str | None, ProgressUpdate] = {}
        if runtime is None or task is None:
            # Some tests instantiate an execution context only to exercise local subtask merging helpers.
            self._logger = StructuredLogger(logging.getLogger("tilebox.workflows.noop"))
        else:
            self._logger = runtime.task_logger.bind(task_id=str(task.id))

    def submit_subtask(
        self,
        task: TaskInstance,
        depends_on: FutureTask | list[FutureTask] | None = None,
        cluster: str | None = None,
        max_retries: int = 0,
        optional: bool = False,
    ) -> FutureTask:
        dependencies: list[int] = []

        if depends_on is None:
            depends_on = []
        elif isinstance(depends_on, FutureTask):
            depends_on = [depends_on]
        elif not isinstance(depends_on, list):
            raise TypeError(f"Invalid dependency. Expected FutureTask or list[FutureTask], got {type(depends_on)}")

        for dep in depends_on:
            if not isinstance(dep, FutureTask):
                raise TypeError(f"Invalid dependency. Expected FutureTask, got {type(dep)}")
            if dep.index >= len(self._sub_tasks):
                raise ValueError(f"Dependent task {dep.index} does not exist")
            dependencies.append(dep.index)
        subtask = FutureTask(
            index=len(self._sub_tasks),
            task=task,
            # cyclic dependencies are not allowed, they are detected by the server and will result in an error
            depends_on=dependencies,
            cluster=cluster,
            max_retries=max_retries,
            optional=optional,
        )
        self._sub_tasks.append(subtask)
        return subtask

    def submit_subtasks(
        self,
        tasks: Sequence[TaskInstance],
        depends_on: FutureTask | list[FutureTask] | None = None,
        cluster: str | None = None,
        max_retries: int = 0,
        optional: bool = False,
    ) -> list[FutureTask]:
        return [
            self.submit_subtask(
                task, cluster=cluster, max_retries=max_retries, depends_on=depends_on, optional=optional
            )
            for task in tasks
        ]

    def submit_batch(
        self, tasks: Sequence[TaskInstance], cluster: str | None = None, max_retries: int = 0
    ) -> list[FutureTask]:
        warn(
            "submit_batch is deprecated, use submit_subtasks instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.submit_subtasks(tasks, cluster=cluster, max_retries=max_retries)

    def progress(self, label: str | None = None) -> ProgressUpdate:
        if label == "":
            label = None

        if label in self._progress_indicators:
            return self._progress_indicators[label]

        # this is our server side limit to prevent mistakes / abuse, so let's not allow to go beyond that already
        # client side
        if len(self._progress_indicators) > _MAX_TASK_PROGRESS_INDICATORS:
            raise ValueError(f"Cannot create more than {_MAX_TASK_PROGRESS_INDICATORS} progress indicators per task.")

        progress_bar = ProgressUpdate(label)
        self._progress_indicators[label] = progress_bar
        return progress_bar

    @property
    def runner_context(self) -> RunnerContext:
        if self._runner is None:
            return RunnerContext()
        return self._runner.context

    @property
    def logger(self) -> StructuredLogger:
        return self._logger

    @property
    def tracer(self) -> WorkflowTracer:
        if self._runner is None:
            return NoopWorkflowTracer()
        return self._runner.tracer


def _finalize_mutable_progress_trackers(
    progress_bars: dict[str | None, ProgressUpdate],
) -> list[ProgressIndicator]:
    return [ProgressIndicator(label, bar._total, bar._done) for label, bar in progress_bars.items()]  # noqa: SLF001


def _execute(task: TaskInstance, context: ExecutionContext) -> None:
    return task.execute(context)


@contextmanager
def _null_task_execution_context(task: Task, context: ExecutionContext) -> Iterator[None]:  # noqa: ARG001
    yield
