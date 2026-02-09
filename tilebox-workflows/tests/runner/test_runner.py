import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from _tilebox.grpc.replay import open_recording_channel, open_replay_channel
from tilebox.workflows import ExecutionContext, Task
from tilebox.workflows.cache import InMemoryCache, JobCache
from tilebox.workflows.client import Client
from tilebox.workflows.data import JobState, ProgressIndicator, RunnerContext, TaskState
from tilebox.workflows.runner.task_runner import TaskRunner


def int_to_bytes(n: int) -> bytes:
    return n.to_bytes(1, "big")  # python3.10 still requires arguments for length and byteorder


def bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")  # python3.10 still requires argument for byteorder


class FibonacciTask(Task):
    n: int

    def execute(self, context: ExecutionContext) -> None:
        cache: JobCache = context.job_cache  # ty: ignore[unresolved-attribute]
        key = f"fib_{self.n}"
        if f"fib_{self.n}" in cache:
            # If the result is already in the cache, we can skip the calculation
            return

        if self.n <= 2:  # Base cases: fib(1) = fib(2) = 1
            cache[key] = int_to_bytes(1)
        else:
            # Calculate fib(n) = fib(n-1) + fib(n-2)
            fib_n_1 = context.submit_subtask(FibonacciTask(self.n - 1))
            fib_n_2 = context.submit_subtask(FibonacciTask(self.n - 2))

            # Sum up results in a final task
            context.submit_subtask(SumResultTask(self.n), depends_on=[fib_n_1, fib_n_2])


class SumResultTask(Task):
    n: int

    def execute(self, context: ExecutionContext) -> None:
        cache: JobCache = context.job_cache  # ty: ignore[unresolved-attribute]
        fib_n_1 = bytes_to_int(cache[f"fib_{self.n - 1}"])
        fib_n_2 = bytes_to_int(cache[f"fib_{self.n - 2}"])

        # Calculate and store result
        cache[f"fib_{self.n}"] = int_to_bytes(fib_n_1 + fib_n_2)


def test_runner_with_fibonacci_workflow() -> None:
    client = replay_client("fibonacci_workflow.rpcs.bin")
    n = 7  # compute fib(7)
    with patch("tilebox.workflows.jobs.client.get_trace_parent_of_current_span") as get_trace_parent_mock:
        # we hardcode the trace parent for the job, which allows us to assert that every single outgoing request
        # matches exactly byte for byte
        get_trace_parent_mock.return_value = "00-f8d3b65869f638c5bfe173ffb3b3e5a0-ccf5709467cafc52-01"
        job = client.jobs().submit("fibonacci", FibonacciTask(n))

    cache = InMemoryCache()
    runner = client.runner(tasks=[FibonacciTask, SumResultTask], cache=cache)
    runner.run_all()

    job_cache = cache.group(str(job.id))
    fibonacci_numbers = [bytes_to_int(job_cache[f"fib_{i}"]) for i in range(1, n + 1)]
    assert fibonacci_numbers == [1, 1, 2, 3, 5, 8, 13]


class FlakyTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        cache: JobCache = context.job_cache  # ty: ignore[unresolved-attribute]
        if "succeed" in cache:
            return  # finally succeed

        raise ValueError("This task always fails if the cache doesn't contain 'succeed'")


def test_runner_with_flaky_task() -> None:
    client = replay_client("flaky_task.rpcs.bin")
    job_client = client.jobs()

    with patch("tilebox.workflows.jobs.client.get_trace_parent_of_current_span") as get_trace_parent_mock:
        # we hardcode the trace parent for the job, which allows us to assert that every single outgoing request
        # matches exactly byte for byte
        get_trace_parent_mock.return_value = "00-9680c9bfd602c4befe7b65a33a7b886d-3de78304f4cfbc40-01"
        job = client.jobs().submit("flaky-task", FlakyTask())

    cache = InMemoryCache()
    runner = client.runner(tasks=[FlakyTask], cache=cache)

    runner.run_all()  # task will fail
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.FAILED

    job_client.retry(job)
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.RUNNING

    runner.run_all()  # task will still fail
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.FAILED  # since it failed

    job_client.retry(job)
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.RUNNING

    cache.group(str(job.id))["succeed"] = b"1"
    runner.run_all()  # now task will succeed
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.COMPLETED


class ProgressTask(Task):
    n: int

    def execute(self, context: ExecutionContext) -> None:
        context.progress("test").add(self.n)
        context.submit_subtasks([ProgressLeafTask(i) for i in range(self.n)])


class ProgressLeafTask(Task):
    i: int

    def execute(self, context: ExecutionContext) -> None:
        context.progress("test").done(1)


def test_runner_with_workflow_tracking_progress() -> None:
    client = replay_client("progress.rpcs.bin")
    job_client = client.jobs()

    with patch("tilebox.workflows.jobs.client.get_trace_parent_of_current_span") as get_trace_parent_mock:
        # we hardcode the trace parent for the job, which allows us to assert that every single outgoing request
        # matches exactly byte for byte
        get_trace_parent_mock.return_value = "00-98b9c13dbc61637ffb36f592a8236088-bc29f6909f0b7c5b-01"
        job = client.jobs().submit("progress-task", ProgressTask(4))

    cache = InMemoryCache()
    runner = client.runner(tasks=[ProgressTask, ProgressLeafTask], cache=cache)

    runner.run_all()
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.COMPLETED
    assert job.progress == [ProgressIndicator("test", 4, 4)]


def replay_client(replay_file: str, assert_request_matches: bool = True) -> Client:
    replay = Path(__file__).parent / "testdata" / "recordings" / replay_file
    replay_channel = open_replay_channel(replay, assert_request_matches)

    with patch("tilebox.workflows.client.open_channel") as open_channel_mock:
        open_channel_mock.return_value = replay_channel
        # url/token doesn't matter since its a mocked channel
        client = Client(
            url="https://api.tilebox.com",
            token="token",  # noqa: S106
        )
        open_channel_mock.assert_called_once()

    return client


def record_client(recording_file: str) -> Client:
    recording = Path(__file__).parent / "testdata" / "recordings" / recording_file
    # this will open a channel to api.tilebox.com, which will send real requests to the server, and record them
    # for later offline replay
    recording_channel = open_recording_channel(
        "https://api.tilebox.com", os.environ["TILEBOX_OPENDATA_ONLY_API_KEY"], recording
    )

    with patch("tilebox.workflows.client.open_channel") as open_channel_mock:
        open_channel_mock.return_value = recording_channel
        # url/token doesn't matter since its a mocked channel
        client = Client(url="https://api.tilebox.com", token="token")  # noqa: S106
        open_channel_mock.assert_called_once()

    return client


class ExplicitIdentifierTaskV1(Task):
    @classmethod
    def identifier(cls) -> tuple[str, str]:
        return "tilebox.com/explicit", "v1.0"

    def execute(self, context: ExecutionContext) -> None:
        pass


class ExplicitIdentifierTaskV2(Task):
    @classmethod
    def identifier(cls) -> tuple[str, str]:
        return "tilebox.com/explicit", "v2.0"

    def execute(self, context: ExecutionContext) -> None:
        pass


def test_runner_disallow_duplicate_task_identifiers() -> None:
    runner = TaskRunner(
        MagicMock(),
        "dummy-cluster",
        InMemoryCache(),
        None,
        None,
        MagicMock(),
        RunnerContext(),
    )

    runner.register(FlakyTask)
    with pytest.raises(
        ValueError,
        match=re.escape("Duplicate task identifier: A task 'FlakyTask' with version 'v0.0' is already registered."),
    ):
        runner.register(FlakyTask)

    runner.register(SumResultTask)
    with pytest.raises(
        ValueError,
        match=re.escape("Duplicate task identifier: A task 'SumResultTask' with version 'v0.0' is already registered."),
    ):
        runner.register(SumResultTask)

    runner.register(ExplicitIdentifierTaskV1)
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Duplicate task identifier: A task 'tilebox.com/explicit' with version 'v1.0' is already registered."
        ),
    ):
        runner.register(ExplicitIdentifierTaskV1)

    runner.register(ExplicitIdentifierTaskV2)  # this one has a different version, so it's fine
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Duplicate task identifier: A task 'tilebox.com/explicit' with version 'v2.0' is already registered."
        ),
    ):
        runner.register(ExplicitIdentifierTaskV2)


class OptionalSubbranch(Task):
    def execute(self, context: ExecutionContext) -> None:
        context.submit_subtask(OptionalSubtasks(False), optional=True)
        context.submit_subtask(SucceedingTask())


class OptionalSubtasks(Task):
    failing_task_optional: bool

    def execute(self, context: ExecutionContext) -> None:
        f = context.submit_subtask(FailingTask(), optional=self.failing_task_optional)
        context.submit_subtask(SucceedingTask(), depends_on=[f])


class FailingTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        cache = context.job_cache  # ty: ignore[unresolved-attribute]
        cache["failing_task"] = b"1"  # to make sure it actually ran
        raise ValueError("This task always fails")


class SucceedingTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        cache = context.job_cache  # ty: ignore[unresolved-attribute]
        cache["succeeding_task"] = b"1"  # to make sure it actually ran


def test_runner_optional_subbranch() -> None:
    client = replay_client("optional_subbranch.rpcs.bin")
    job_client = client.jobs()

    with patch("tilebox.workflows.jobs.client.get_trace_parent_of_current_span") as get_trace_parent_mock:
        # we hardcode the trace parent for the job, which allows us to assert that every single outgoing request
        # matches exactly byte for byte
        get_trace_parent_mock.return_value = "00-42fe17a0cc6752adf16a5a326d37f51c-795dd6a3bc5a0b81-01"
        job = client.jobs().submit("optional-subbranch-test", OptionalSubbranch())

    cache = InMemoryCache()
    runner = client.runner(tasks=[OptionalSubbranch, OptionalSubtasks, FailingTask, SucceedingTask], cache=cache)

    runner.run_all()
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.COMPLETED

    assert job.execution_stats.tasks_by_state[TaskState.COMPUTED] == 3
    assert job.execution_stats.tasks_by_state[TaskState.FAILED_OPTIONAL] == 1
    assert job.execution_stats.tasks_by_state[TaskState.SKIPPED] == 1

    assert cache.group(str(job.id))["failing_task"] == b"1"
    assert cache.group(str(job.id))["succeeding_task"] == b"1"


def test_runner_optional_subtask() -> None:
    client = replay_client("optional_subtask.rpcs.bin")
    job_client = client.jobs()

    with patch("tilebox.workflows.jobs.client.get_trace_parent_of_current_span") as get_trace_parent_mock:
        # we hardcode the trace parent for the job, which allows us to assert that every single outgoing request
        # matches exactly byte for byte
        get_trace_parent_mock.return_value = "00-154ffe629cc5b746584825bfbb37963d-3ed10512af70309c-01"
        job = client.jobs().submit("optional-subtasks-test", OptionalSubtasks(True))

    cache = InMemoryCache()
    runner = client.runner(tasks=[OptionalSubtasks, FailingTask, SucceedingTask], cache=cache)

    runner.run_all()
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.COMPLETED

    assert job.execution_stats.tasks_by_state[TaskState.COMPUTED] == 2
    assert job.execution_stats.tasks_by_state[TaskState.FAILED_OPTIONAL] == 1

    assert cache.group(str(job.id))["failing_task"] == b"1"
    assert cache.group(str(job.id))["succeeding_task"] == b"1"
