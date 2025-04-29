import contextlib
import json
import logging
import random
import signal
import threading
from base64 import b64encode
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import timedelta
from functools import partial
from multiprocessing import get_context
from multiprocessing.context import SpawnProcess
from queue import Empty, Queue
from threading import Event
from time import sleep
from types import FrameType, TracebackType
from typing import Any, TypeAlias, TypeVar
from uuid import UUID
from warnings import warn

from loguru import logger
from opentelemetry.trace.status import StatusCode
from tenacity import retry, retry_if_exception_type, stop_when_event_set, wait_random_exponential
from tenacity.stop import stop_base

from _tilebox.grpc.channel import open_channel
from _tilebox.grpc.error import InternalServerError
from tilebox.datasets.sync.dataset import DatasetClient
from tilebox.workflows.cache import JobCache
from tilebox.workflows.data import ComputedTask, NextTaskToRun, Task, TaskLease
from tilebox.workflows.interceptors import Interceptor, InterceptorType
from tilebox.workflows.observability.logging import get_logger
from tilebox.workflows.observability.tracing import WorkflowTracer
from tilebox.workflows.runner.task_service import TaskService
from tilebox.workflows.task import ExecutionContext as ExecutionContextBase
from tilebox.workflows.task import FutureTask, RunnerContext, TaskMeta
from tilebox.workflows.task import Task as TaskInstance

# In seconds
_SHUTDOWN_GRACE_PERIOD = timedelta(seconds=2)
_POLL_INTERVAL = timedelta(seconds=5)
_JITTER_INTERVAL = timedelta(seconds=5)
_INITIAL_RETRY_BACKOFF = timedelta(seconds=5)
_MAX_RETRY_BACKOFF = timedelta(hours=1)  # 1 hour

WrappedFnReturnT = TypeVar("WrappedFnReturnT")


def _retry_backoff(func: Callable[..., WrappedFnReturnT], stop: stop_base) -> Callable[..., WrappedFnReturnT]:
    """Wrap a function with an exponential backoff retry strategy.

    Args:
        func: The function to wrap
        stop: A stop condition for the retry strategy

    Returns:
        The wrapped function
    """
    return retry(  # type: ignore[no-any-return]
        retry=retry_if_exception_type(InternalServerError),
        stop=stop,
        wait=wait_random_exponential(
            multiplier=_INITIAL_RETRY_BACKOFF.total_seconds(), max=_MAX_RETRY_BACKOFF.total_seconds()
        ),
    )(func)


def lease_renewer(
    url: str, token: str | None, new_leases: Queue[tuple[UUID, TaskLease]], done_tasks: Queue[UUID]
) -> None:
    channel = open_channel(url, token)
    service = TaskService(channel)

    while True:
        # Block until we receive a task to extend the lease for
        task_id, task_lease = new_leases.get()
        _extend_lease_while_task_is_running(service, task_id, task_lease, done_tasks)


def _extend_lease_while_task_is_running(
    service: TaskService,
    task_id: UUID,
    task_lease: TaskLease,
    done_tasks: Queue[UUID],
) -> UUID | None:
    while True:
        try:
            done_task = done_tasks.get(block=True, timeout=task_lease.recommended_wait_until_next_extension)
        except Empty:
            done_task = None

        if done_task is not None:
            if done_task != task_id:  # queues should be in right order
                logger.error(f"Lease extension task id mismatch: {done_task=}, but expected {task_id=}")

            break

        logger.info(f"Extending task lease for {task_id=}, {task_lease=}")
        try:
            # The first time we call the function, we pass the argument we received
            # After that, we call it with the result of the previous call
            task_lease = service.extend_task_lease(task_id, 2 * task_lease.lease)
            if task_lease.lease == 0:
                # The server did not return a lease extension, it means that there is no need in trying to extend the lease
                logger.info(f"task lease extension not granted for task {task_id}")
                # even though we failed to extend the lease, let's still wait till the task is done
                # otherwise we might end up with a mismatch between the task currently being executed and the task
                # that we extend leases for (and the runner can anyways only execute one task at a time)
                done_task = done_tasks.get()
                if done_task != task_id:  # queues should be in right order
                    logger.error(
                        f"Lease extension task id mismatch after failed lease extension: {done_task=}, but expected {task_id=}"
                    )
                return

        except InternalServerError as e:
            logger.error(f"Failed to extend lease for task {task_id} with error {e}")

            # same as above, let's wait till the task is done to avoid a mismatch between the executed task and lease
            done_task = done_tasks.get()
            if done_task != task_id:  # queues should be in right order
                logger.error(
                    f"Lease extension task id mismatch after failed lease extension: {done_task=}, but expected {task_id=}"
                )

            # There is no point in trying to extend the lease again because it most probably will be expired then
            return


class _LeaseRenewer(SpawnProcess):
    """Daemon process to extend the lease for a task whenever necessary."""

    def __init__(self, url: str, token: str | None) -> None:
        super().__init__(daemon=True)
        self._url = url
        self._token = token

        # we don't want to fork the current process, but instead spawn a new one
        # therefore we need to use the spawn context to create the queues
        ctx = get_context("spawn")
        self._new_leases: Queue[tuple[UUID, TaskLease]] = ctx.Queue()  # type: ignore[assignment]
        self._done_tasks: Queue[UUID] = ctx.Queue()  # type: ignore[assignment]

    def run(self) -> None:
        lease_renewer(self._url, self._token, self._new_leases, self._done_tasks)

    @contextmanager
    def lease_extension(self, task_id: UUID, task_lease: TaskLease) -> Iterator[None]:
        """Context manager to extend the lease for a task."""
        logger.debug(f"Task {task_id} started")
        self._new_leases.put((task_id, task_lease))
        try:
            yield None
        finally:
            self._done_tasks.put(task_id)
            logger.debug(f"Task {task_id} completed")


_HANDLER: TypeAlias = Callable[[int, FrameType | None], Any] | int | signal.Handlers | None


class RunnerShutdown(Exception):  # noqa: N818
    pass


class _GracefulShutdown:
    def __init__(self, grace_period: timedelta, service: TaskService) -> None:
        """
        Graceful shutdown is a context manager that can be used to delay SIGTERM and SIGINT signals for a grace period.
        That way work can finish cleanly before the process is terminated.

        Workers can check if they should shut down by calling the is_shutting_down method.

        After the grace period has passed, the same signal will be re-raised.

        It has special support for marking a task as failed immediately on interrupt, which is done if we are
        currently executing a tasks execute function, since this is user code and we have no control over how long it
        takes to execute.

        Args:
            grace_period: Timedelta to delay the signal by in order to enable a graceful shutdown.
            service: A reference to the task service, so that we can mark a task as failed on interrupt if necessary.
        """

        self._interrupted = Event()
        self._grace_period = grace_period
        self._service = service

        self._original_sigterm: _HANDLER = None
        self._original_sigint: _HANDLER = None

        # special handling for marking a task as failed on interrupt
        self._task_mutex = threading.Lock()
        self._task: Task | None = None

    def _external_interrupt_handler(self, signum: int, frame: FrameType | None) -> None:
        """Signal handler for SIGTERM and SIGINT."""
        self._interrupted.set()

        with self._task_mutex:
            if self._task is not None:
                self._service.task_failed(self._task, RunnerShutdown("Task was interrupted"), cancel_job=False)

        # fetch the handler we want to call after the grace period
        original_handler = self._original_sigterm if signum == signal.SIGTERM else self._original_sigint

        # restore default signal handler, so that when we interrupt a second time, the process will exit for sure
        self._revert_to_original_signal_handlers()

        if not callable(original_handler):
            original_handler = signal.default_int_handler

        with self._task_mutex:
            if self._task is not None:
                # if a task is currently running let's delay for the grace period, and then call the original handler
                sleep(self._grace_period.total_seconds())

        # this will stop the process:
        original_handler(signum, frame)

    def is_shutting_down(self) -> bool:
        """Check whether an interrupt signal has been received."""
        return self._interrupted.is_set()

    def stop_if_shutting_down(self) -> stop_base:
        """Used as a stop condition for tenacity retries. If the runner is shutting down, don't retry any requests."""
        return stop_when_event_set(self._interrupted)

    def sleep(self, seconds: float) -> None:
        """Sleep for a given number of seconds, or until an interrupt signal is received."""
        self._interrupted.wait(seconds)

    def __enter__(self) -> "_GracefulShutdown":
        """Enter a graceful shutdown context. Intercepts SIGTERM and SIGINT signals and delays them by a grace period."""
        self._original_sigterm = signal.signal(signal.SIGTERM, self._external_interrupt_handler)
        self._original_sigint = signal.signal(signal.SIGINT, self._external_interrupt_handler)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Exit a graceful shutdown context. Restores the original signal handlers."""
        self._revert_to_original_signal_handlers()

    def _revert_to_original_signal_handlers(self) -> None:
        if self._original_sigint is None or self._original_sigterm is None:
            return

        signal.signal(signal.SIGTERM, self._original_sigterm)
        signal.signal(signal.SIGINT, self._original_sigint)

        self._original_sigint = None
        self._original_sigterm = None

    @contextmanager
    def mark_task_as_failed_on_interrupt(self, task: Task) -> Iterator[None]:
        """
        A context manager to enable marking a task as failed immediately on interrupt.

        Only while the context manager is active the task will be marked as failed on interrupt. This is useful to
        wrap the execution of a task, since we have no way of knowing how long it will take to execute, its user code.
        """
        with self._task_mutex:
            self._task = task
        try:
            yield
        finally:
            with self._task_mutex:
                self._task = None


class TaskRunner:
    def __init__(  # noqa: PLR0913
        self,
        service: TaskService,
        cluster: str,
        cache: JobCache,
        tracer: WorkflowTracer | None,
        logger: logging.Logger | None,
        lease_renewer: _LeaseRenewer,
        context: RunnerContext,
    ) -> None:
        self._service = service
        self.tasks_to_run = NextTaskToRun(cluster_slug=cluster, identifiers={})
        self.cache = cache
        self.tracer = tracer or WorkflowTracer()
        self.logger = logger or get_logger("runner.TaskRunner", level=logging.WARNING)
        self._interceptors: list[Interceptor] = []
        self._lease_renewer = lease_renewer
        self._lease_renewer.start()  # Start the lease extension process in the background
        self._context = context

    def register(self, task: type) -> None:
        """Register a task that can be executed by the task runner.

        Args:
            task: The task to register.
        """
        meta = TaskMeta.for_task(task)  # ensures that this is a valid task
        if not meta.executable:
            task_repr = task.__name__
            if meta.identifier.name != task.__name__:
                task_repr += f" ({meta.identifier.name})"
            raise ValueError(
                f"Task {task_repr} is not executable. It must have an execute method in order to "
                f"register it with a task runner."
            )
        self.tasks_to_run.identifiers[meta.identifier] = task

    def add_interceptor(self, interceptor: InterceptorType) -> None:
        """Add an interceptor to the task runner.

        Args:
            interceptor: The interceptor to add.
        """
        if not hasattr(interceptor, "__original_interceptor_func__"):
            raise ValueError("Interceptor must be created with @execution_interceptor decorator.")
        self._interceptors.append(interceptor.__original_interceptor_func__)

    def run_forever(self) -> None:
        """
        Run the task runner forever. This will poll for new tasks and execute them as they come in.
        If no tasks are available, it will sleep for a short time and then try again.
        """
        self._run(stop_when_idling=False)

    def run_all(self) -> None:
        """
        Run the task runner and execute all tasks, until there are no more tasks available.
        """
        self._run(stop_when_idling=True)

    def _run(self, stop_when_idling: bool = True) -> None:
        """
        Run the task runner forever. This will poll for new tasks and execute them as they come in.
        If no tasks are available, it will sleep for a short time and then try again.
        """
        task: Task | None = None

        # capture interrupt signals and delay them by a grace period in order to shut down gracefully
        with _GracefulShutdown(_SHUTDOWN_GRACE_PERIOD, self._service) as shutdown_context:
            while True:
                if task is None:  # if we don't have a task right now, let's try to work-steal one
                    if shutdown_context.is_shutting_down():
                        return
                    try:
                        task = self._service.next_task(task_to_run=self.tasks_to_run, computed_task=None)
                    except InternalServerError as e:
                        # We do not need to retry here, since the task runner will sleep for a while and then anyways request this again.
                        self.logger.error(f"Failed to get next task with error {e}")

                if task is not None:  # we have a task to execute
                    if task.retry_count > 0:
                        self.logger.debug(f"Retrying task {task.id} that failed {task.retry_count} times")
                    task = self._execute(task, shutdown_context)  # submitting the task gives us the next one
                else:  # if we didn't get a task, let's sleep for a bit and try work-stealing again
                    self.logger.debug("No task to run")
                    if stop_when_idling:  # if stop_when_idling is set, we can just return
                        return
                    # now sleep for a bit and then try again, unless we receive an interrupt
                    shutdown_context.sleep(
                        _POLL_INTERVAL.total_seconds() + random.uniform(0, _JITTER_INTERVAL.total_seconds())  # noqa: S311
                    )
                    if shutdown_context.is_shutting_down():
                        return

    def _execute(self, task: Task, shutdown_context: _GracefulShutdown) -> Task | None:
        try:
            return self._try_execute(task, shutdown_context)
        except Exception as e:
            task_repr = str(task.id)
            # let's try to get the name of the task class for a better error message:
            # otherwise, if it's not possible, we just log the task id
            with contextlib.suppress(KeyError):
                task_repr = self.tasks_to_run.identifiers[task.identifier].__name__
            self.logger.exception(f"Task {task_repr} failed!")

            task_failed_retry = _retry_backoff(self._service.task_failed, stop=shutdown_context.stop_if_shutting_down())
            task_failed_retry(task, e)
        return None

    def _try_execute(self, task: Task, shutdown_context: _GracefulShutdown) -> Task | None:
        if task.job is None:
            raise ValueError(f"Task {task.id} has no job associated with it.")

        if task.lease is None:
            raise ValueError(f"Task {task.id} has no lease associated with it.")

        with (
            self._lease_renewer.lease_extension(task.id, task.lease),
            self.tracer.start_job_span(task.job, f"task/{task.id}") as span,
        ):
            try:
                try:
                    task_class = self.tasks_to_run.identifiers[task.identifier]
                except KeyError:
                    self.logger.error(f"Task {task.id} has unknown task identifier {task.identifier}")
                    raise ValueError(f"Task {task.id} has unknown task identifier {task.identifier}") from None

                # now that we've successfully looked up the task class, we can update the span name to replace the
                # task execution id with the task class name
                span.update_name(f"task/{task_class.__name__}")

                try:
                    task_instance = task_class._deserialize(task.input, self._context)  # noqa: SLF001
                except json.JSONDecodeError:
                    self.logger.exception(f"Failed to deserialize input for task execution {task.id}")
                    raise ValueError(f"Failed to deserialize input for task execution {task.id}") from None

                # record the task input as a span attribute, but for this we need to convert it to a string
                # in case of binary data, we base64 encode it (e.g. protobuf message content)
                task_input_span_attr = ""
                if task.input is not None:
                    try:
                        task_input_span_attr = task.input.decode("utf-8")
                    except UnicodeDecodeError:
                        task_input_span_attr = b64encode(task.input).decode("ascii")
                span.set_attribute("task.input", task_input_span_attr)

                context = ExecutionContext(self, task, self.cache.group(str(task.job.id)))

                # if we receive an interrupt exactly when running the user defined execute function, it is quite
                # likely that we don't finish in time. So we mark the task as failed in that case immediately.
                # If for some reason it does finish in time, the failed status will be overwritten by the computed
                # status done later on in this function.
                with shutdown_context.mark_task_as_failed_on_interrupt(task):
                    _execute(task_instance, context, self._interceptors)

                # if we received a stop signal, we should not request a next task
                request_new_task = not shutdown_context.is_shutting_down()
                task_to_run = self.tasks_to_run if request_new_task else None

                next_task_retry = _retry_backoff(self._service.next_task, stop=shutdown_context.stop_if_shutting_down())
                # mark the task as computed and get the next one
                return next_task_retry(
                    task_to_run=task_to_run,
                    computed_task=ComputedTask(
                        id=task.id,
                        display=task.display,
                        sub_tasks=[
                            task.to_submission(self.tasks_to_run.cluster_slug)
                            for task in context._sub_tasks  # noqa: SLF001
                        ],
                    ),
                )

            except Exception as e:  # noqa: BLE001
                # catch all exceptions and re-raise them, since we just want to mark spans as failed
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, "Task failed with exception")
                raise e from None  # reraise, since we just wanted to mark it as failed in the span


class ExecutionContext(ExecutionContextBase):
    def __init__(self, runner: TaskRunner, task: Task, job_cache: JobCache) -> None:
        self._runner = runner
        self.current_task = task
        self.job_cache = job_cache
        self._sub_tasks: list[FutureTask] = []

    def submit_subtask(
        self,
        task: TaskInstance,
        depends_on: list[FutureTask] | None = None,
        cluster: str | None = None,
        max_retries: int = 0,
    ) -> FutureTask:
        subtask = FutureTask(
            index=len(self._sub_tasks),
            task=task,
            # cyclic dependencies are not allowed, they are detected by the server and will result in an error
            depends_on=[d.index for d in depends_on] if depends_on is not None else [],
            cluster=cluster,
            max_retries=max_retries,
        )
        self._sub_tasks.append(subtask)
        return subtask

    def submit_subtasks(
        self, tasks: Sequence[TaskInstance], cluster: str | None = None, max_retries: int = 0
    ) -> list[FutureTask]:
        return [self.submit_subtask(task, cluster=cluster, max_retries=max_retries) for task in tasks]

    def submit_batch(
        self, tasks: Sequence[TaskInstance], cluster: str | None = None, max_retries: int = 0
    ) -> list[FutureTask]:
        warn(
            "submit_batch is deprecated, use submit_subtasks instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.submit_subtasks(tasks, cluster, max_retries)

    @property
    def runner_context(self) -> RunnerContext:
        return self._runner._context  # noqa: SLF001

    def _dataset(self, dataset_id: str) -> DatasetClient:
        """Needed by the timeseries integration, to resolve a dataset id to a RemoteTimeseriesDataset."""
        client = self._runner._context.datasets_client  # noqa: SLF001
        if client is None:
            raise ValueError("No datasets client configured.")

        return client.dataset(dataset_id)


def _execute(task: TaskInstance, context: ExecutionContext, additional_interceptors: list[Interceptor]) -> None:
    interceptors: list[Interceptor] = additional_interceptors + TaskMeta.for_task(task).interceptors

    # chain interceptors in reverse order before eventually calling the actual task.execute function:
    next_func = task.execute
    for interceptor in interceptors[::-1]:
        next_func = partial(interceptor, task, next_func)

    return next_func(context)  # call the first func in the chain, it will call the next one and so on
