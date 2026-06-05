from __future__ import annotations

import json
import logging
from base64 import b64encode
from collections.abc import Callable, Iterator, MutableMapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING
from uuid import UUID
from warnings import warn

from opentelemetry.trace.status import StatusCode

from tilebox.workflows.cache import JobCache
from tilebox.workflows.data import (
    ComputedTask,
    FailedTask,
    ProgressIndicator,
    StorageLocation,
    Task,
)
from tilebox.workflows.observability.logging import StructuredLogger
from tilebox.workflows.observability.tracing import NoopWorkflowTracer, WorkflowTracer, start_job_span
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.task import ExecutionContext as ExecutionContextBase
from tilebox.workflows.task import FutureTask, ProgressUpdate, RunnerContext, merge_future_tasks_to_submissions
from tilebox.workflows.task import Task as TaskInstance

if TYPE_CHECKING:
    from tilebox.workflows.client import Client

_MAX_TASK_PROGRESS_INDICATORS = 1000


class TaskExecutor:
    def __init__(  # noqa: PLR0913
        self,
        runner: Runner,
        cache: JobCache,
        tracer: WorkflowTracer,
        task_logger: StructuredLogger,
        runner_context: RunnerContext,
        fallback_cluster: str,
    ) -> None:
        self.runner = runner
        self.cache = cache
        self.tracer = tracer
        self.task_logger = task_logger
        self.fallback_cluster = fallback_cluster
        self.runner_context = runner_context

    def execute_task(
        self,
        task: Task,
        wrap_execute_context_manager: Callable[[Task, ExecutionContext], AbstractContextManager[None]] | None = None,
    ) -> ComputedTask | FailedTask:
        context: ExecutionContext | None = None
        try:
            if task.job is None:
                self.task_logger.error(f"Task {task.id} has no job associated with it.", task_id=str(task.id))
                return FailedTask(task.id, task.display, was_workflow_error=False, progress_updates=[])

            try:
                task_class = self.runner.tasks_by_identifier[task.identifier]
            except KeyError:
                self.task_logger.error(
                    f"Task {task.id} has unknown identifier {task.identifier}.",
                    task_id=str(task.id),
                    identifier=str(task.identifier),
                )
                return FailedTask(task.id, task.display, was_workflow_error=False, progress_updates=[])

            context = ExecutionContext(self, task, self.cache.group(str(task.job.id)))
            if wrap_execute_context_manager is None:
                wrap_execute_context_manager = _noop_context_manager

            with start_job_span(self.tracer, task.job, f"task/{task.id}") as span:
                task_repr = task_class.__name__
                span.update_name(f"task/{task_repr}")
                span.set_attribute("task_id", str(task.id))
                span.set_attribute("identifier.name", task.identifier.name)
                span.set_attribute("identifier.version", task.identifier.version)

                try:
                    task_instance = task_class._deserialize(task.input, self.runner_context)  # noqa: SLF001
                    _set_task_input_span_attribute(span, task.input)
                    with wrap_execute_context_manager(task, context):
                        _execute(task_instance, context)

                    return ComputedTask(
                        id=task.id,
                        display=task.display,
                        sub_tasks=merge_future_tasks_to_submissions(
                            context._sub_tasks,  # noqa: SLF001
                            self.fallback_cluster,
                        ),
                        progress_updates=_finalize_mutable_progress_trackers(context._progress_indicators),  # noqa: SLF001
                    )
                except json.JSONDecodeError:
                    workflow_error = ValueError(f"Failed to deserialize input for task execution {task.id}")
                    span.record_exception(workflow_error)
                    span.set_status(StatusCode.ERROR, "Task failed with exception")
                    return FailedTask.from_task_error(
                        task,
                        workflow_error,
                        was_workflow_error=True,
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
        except Exception as error:  # noqa: BLE001
            progress_updates = []
            if context is not None:
                progress_updates = _finalize_mutable_progress_trackers(context._progress_indicators)  # noqa: SLF001
            return FailedTask.from_task_error(
                task,
                error,
                was_workflow_error=False,
                progress_updates=progress_updates,
            )


class ExecutionContext(ExecutionContextBase):
    def __init__(self, executor: TaskExecutor, task: Task, job_cache: JobCache) -> None:
        self._executor = executor
        self.current_task = task
        self.job_cache = job_cache
        self._sub_tasks: list[FutureTask] = []
        self._progress_indicators: dict[str | None, ProgressUpdate] = {}
        if executor is None or task is None:
            # Some tests instantiate an execution context only to exercise local subtask merging helpers.
            self._logger = StructuredLogger(logging.getLogger("tilebox.workflows.noop"))
        else:
            self._logger = executor.task_logger.bind(task_id=str(task.id))

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
        if self._executor is None:
            return RunnerContext()
        return self._executor.runner_context

    @property
    def logger(self) -> StructuredLogger:
        return self._logger

    @property
    def tracer(self) -> WorkflowTracer:
        if self._executor is None:
            return NoopWorkflowTracer()
        return self._executor.tracer


class LazyStorageLocations(MutableMapping[UUID, StorageLocation]):
    def __init__(self, client: Client, runner_context: RunnerContext) -> None:
        self._client = client
        self._runner_context = runner_context
        self._locations: dict[UUID, StorageLocation] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._locations = {
            location.id: location._with_runner_context(self._runner_context)  # noqa: SLF001
            for location in self._client.automations().storage_locations()
        }
        self._loaded = True

    def __getitem__(self, key: UUID) -> StorageLocation:
        self._load()
        return self._locations[key]

    def __setitem__(self, key: UUID, value: StorageLocation) -> None:
        self._load()
        self._locations[key] = value

    def __delitem__(self, key: UUID) -> None:
        self._load()
        del self._locations[key]

    def __iter__(self) -> Iterator[UUID]:
        self._load()
        return iter(self._locations)

    def __len__(self) -> int:
        self._load()
        return len(self._locations)


def _finalize_mutable_progress_trackers(
    progress_bars: dict[str | None, ProgressUpdate],
) -> list[ProgressIndicator]:
    return [ProgressIndicator(label, bar._total, bar._done) for label, bar in progress_bars.items()]  # noqa: SLF001


def _set_task_input_span_attribute(span: object, task_input: bytes | None) -> None:
    task_input_span_attr = ""
    if task_input is not None:
        try:
            task_input_span_attr = task_input.decode("utf-8")
        except UnicodeDecodeError:
            task_input_span_attr = b64encode(task_input).decode("ascii")
    span.set_attribute("input", task_input_span_attr)  # ty: ignore[unresolved-attribute]


def _execute(task: TaskInstance, context: ExecutionContext) -> None:
    return task.execute(context)


@contextmanager
def _noop_context_manager(task: Task, context: ExecutionContext) -> Iterator[None]:  # noqa: ARG001
    yield
