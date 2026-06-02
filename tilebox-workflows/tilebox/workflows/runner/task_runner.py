import contextlib
import random
import signal
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from multiprocessing import get_context
from multiprocessing.context import SpawnProcess
from queue import Empty, Queue
from threading import Event
from time import sleep
from types import FrameType, TracebackType
from typing import Any, TypeAlias, TypeVar
from uuid import UUID

try:
    from typing import Self  # ty: ignore[unresolved-import]
except ImportError:  # Self is only available in Python 3.11+
    from typing_extensions import Self

from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_when_event_set, wait_random_exponential
from tenacity.stop import stop_base

from _tilebox.grpc.channel import open_channel
from _tilebox.grpc.error import InternalServerError
from tilebox.workflows.cache import JobCache
from tilebox.workflows.data import ComputedTask, FailedTask, Idling, NextTaskToRun, Task, TaskLease
from tilebox.workflows.observability.logging import StructuredLogger
from tilebox.workflows.observability.tracing import WorkflowTracer
from tilebox.workflows.runner.executor import (
    ApiLeaseManager,
    ExecutionContext,
    TaskExecutor,
    _finalize_mutable_progress_trackers,
)
from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.runtime import RunnerRuntime
from tilebox.workflows.runner.task_service import TaskService
from tilebox.workflows.task import RunnerContext
from tilebox.workflows.task import Task as TaskInstance

# The time we give a task to finish it's execution when a runner shutdown is requested before we forcefully stop it
_SHUTDOWN_GRACE_PERIOD = timedelta(seconds=2)

# Retry configuration for retrying failed requests to the workflows API
_INITIAL_RETRY_BACKOFF = timedelta(seconds=5)
_MAX_RETRY_BACKOFF = timedelta(hours=1)  # 1 hour

# A maximum idling duration, as a safeguard to avoid way too long sleep times in case the suggested idling duration is
# ever too long. 5 minutes should be plenty of time to wait.
_MAX_IDLING_DURATION = timedelta(minutes=5)
# A minimum idling duration, as a safeguard to avoid too short sleep times in case the suggested idling duration is
# ever too short.
_MIN_IDLING_DURATION = timedelta(milliseconds=1)

# Fallback polling interval and jitter in case the workflows API fails to respond with a suggested idling duration
_FALLBACK_POLL_INTERVAL = timedelta(seconds=5)
_FALLBACK_JITTER_INTERVAL = timedelta(seconds=5)

# Maximum number of progress bars per task, mirroring the limit on the server side
_MAX_TASK_PROGRESS_INDICATORS = 1000

WrappedFnReturnT = TypeVar("WrappedFnReturnT")


def _retry_backoff(func: Callable[..., WrappedFnReturnT], stop: stop_base) -> Callable[..., WrappedFnReturnT]:
    """Wrap a function with an exponential backoff retry strategy.

    Args:
        func: The function to wrap
        stop: A stop condition for the retry strategy

    Returns:
        The wrapped function
    """
    return retry(
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

        logger.debug(f"Extending task lease for {task_id=}, {task_lease=}")
        try:
            # The first time we call the function, we pass the argument we received
            # After that, we call it with the result of the previous call
            task_lease = service.extend_task_lease(task_id, 2 * task_lease.lease)
            if task_lease.lease == 0:
                # The server did not return a lease extension, it means that there is no need in trying to extend the lease
                logger.debug(f"task lease extension not granted for task {task_id}")
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
        self._new_leases: Queue[tuple[UUID, TaskLease]] = ctx.Queue()
        self._done_tasks: Queue[UUID] = ctx.Queue()

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
        self._context: ExecutionContext | None = None

    def _external_interrupt_handler(self, signum: int, frame: FrameType | None) -> None:
        """Signal handler for SIGTERM and SIGINT."""
        self._interrupted.set()

        with self._task_mutex:
            if self._task is not None:
                progress = []
                if self._context is not None:
                    progress = _finalize_mutable_progress_trackers(self._context._progress_indicators)  # noqa: SLF001
                self._service.task_failed(
                    self._task,
                    RunnerShutdown("Task was interrupted"),
                    was_workflow_error=False,
                    progress_updates=progress,
                )

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

    def __enter__(self) -> Self:
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
    def mark_task_as_failed_on_interrupt(self, task: Task, context: "ExecutionContext") -> Iterator[None]:
        """
        A context manager to enable marking a task as failed immediately on interrupt.

        Only while the context manager is active the task will be marked as failed on interrupt. This is useful to
        wrap the execution of a task, since we have no way of knowing how long it will take to execute, its user code.
        """
        with self._task_mutex:
            self._task = task
            self._context = context
        try:
            yield
        finally:
            with self._task_mutex:
                self._task = None
                self._context = None


class TaskRunner:
    def __init__(  # noqa: PLR0913
        self,
        service: TaskService,
        cluster: str,
        cache: JobCache,
        tracer: WorkflowTracer,
        lease_renewer: _LeaseRenewer,
        context: RunnerContext,
        task_logger: StructuredLogger,
        runner_logger: StructuredLogger,
    ) -> None:
        self._service = service
        self.cache = cache
        self.tracer = tracer
        self.task_logger = task_logger
        self.runner_logger = runner_logger
        self._context = context
        self._runner = Runner(cache=cache)
        self.tasks_to_run = NextTaskToRun(cluster_slug=cluster, identifiers=self._runner.tasks_by_identifier)
        self._lease_renewer = lease_renewer
        self._lease_renewer.start()  # Start the lease extension process in the background
        self._runtime = RunnerRuntime(cache, tracer, task_logger, context)
        self._executor = TaskExecutor(
            self._runner,
            self._runtime,
            fallback_cluster=cluster,
            lease_manager=ApiLeaseManager(lease_renewer),
        )

    def register(self, task: type[TaskInstance]) -> None:
        """Register a task that can be executed by the task runner.

        Args:
            task: The task to register.
        """
        self._runner.register(task)

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

    def _run(self, stop_when_idling: bool = True) -> None:  # noqa: C901
        """
        Run the task runner forever. This will poll for new tasks and execute them as they come in.
        If no tasks are available, it will sleep for a short time and then try again.
        """
        work: Task | Idling | None = None

        # capture interrupt signals and delay them by a grace period in order to shut down gracefully
        with _GracefulShutdown(_SHUTDOWN_GRACE_PERIOD, self._service) as shutdown_context:
            while True:
                if not isinstance(work, Task):  # if we don't have a task right now, let's try to work-steal one
                    if shutdown_context.is_shutting_down():  # unless we received an interrupt, then we shut down
                        return
                    try:
                        work = self._service.next_task(task_to_run=self.tasks_to_run, computed_task=None)
                    except InternalServerError as e:
                        # We do not need to retry here, since the task runner will sleep for a while and then anyways request this again.
                        self.runner_logger.error(f"Failed to get next task with error {e}")

                if isinstance(work, Task):  # we received a task to execute
                    task = work
                    if task.retry_count > 0:
                        self.runner_logger.debug(f"Retrying task {task.id} that failed {task.retry_count} times")
                    work = self._execute(task, shutdown_context)  # submitting the task gives us the next work item
                elif isinstance(work, Idling):  # we received an idling response, so let's sleep for a bit
                    self.runner_logger.debug("No task to run, idling")
                    if stop_when_idling:  # if stop_when_idling is set, we can just return
                        return

                    # now sleep for a bit and then try again, unless we receive an interrupt
                    idling_duration = work.suggested_idling_duration
                    idling_duration = min(idling_duration, _MAX_IDLING_DURATION)
                    idling_duration = max(idling_duration, _MIN_IDLING_DURATION)
                    shutdown_context.sleep(idling_duration.total_seconds())
                    if shutdown_context.is_shutting_down():
                        return
                else:  # work is None
                    # we didn't receive an idling response, but also not a task. This only happens if we didn't request
                    # a task to run, indicating that we are shutting down.
                    if shutdown_context.is_shutting_down():
                        return

                    fallback_interval = _FALLBACK_POLL_INTERVAL.total_seconds() + random.uniform(  # noqa: S311
                        0, _FALLBACK_JITTER_INTERVAL.total_seconds()
                    )
                    self.runner_logger.debug(
                        f"Didn't receive a task to run, nor an idling response, but runner is not shutting down. "
                        f"Falling back to a default idling period of {fallback_interval:.2f}s"
                    )

                    shutdown_context.sleep(fallback_interval)

    def _execute(self, task: Task, shutdown_context: _GracefulShutdown) -> Task | Idling | None:
        if task.job is None:
            raise ValueError(f"Task {task.id} has no job associated with it.")

        task_repr = str(task.id)
        self.runner_logger.debug("Executing task", task=task_repr, input=task.input)
        result = self._executor.execute(task, shutdown_context.mark_task_as_failed_on_interrupt)
        with contextlib.suppress(KeyError):
            task_repr = self.tasks_to_run.identifiers[task.identifier].__name__

        if isinstance(result, ComputedTask):
            request_new_task = not shutdown_context.is_shutting_down()
            task_to_run = self.tasks_to_run if request_new_task else None
            next_task_retry = _retry_backoff(self._service.next_task, stop=shutdown_context.stop_if_shutting_down())
            return next_task_retry(task_to_run=task_to_run, computed_task=result)

        if isinstance(result, FailedTask):
            self.runner_logger.error(f"Task {task_repr} failed!", display=result.display)
            task_failed_retry = _retry_backoff(self._service.task_failed, stop=shutdown_context.stop_if_shutting_down())
            task_failed_retry(result)
            return None

        raise TypeError(f"Unexpected task execution result: {type(result)}")
