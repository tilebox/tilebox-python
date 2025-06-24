import os
from pathlib import Path
from unittest.mock import patch

from _tilebox.grpc.replay import open_recording_channel, open_replay_channel
from tilebox.workflows import ExecutionContext, Task
from tilebox.workflows.cache import InMemoryCache, JobCache
from tilebox.workflows.client import Client
from tilebox.workflows.data import JobState


def int_to_bytes(n: int) -> bytes:
    return n.to_bytes(1, "big")  # python3.10 still requires arguments for length and byteorder


def bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")  # python3.10 still requires argument for byteorder


class FibonacciTask(Task):
    n: int

    def execute(self, context: ExecutionContext) -> None:
        cache: JobCache = context.job_cache  # type: ignore[attr-defined]
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
        cache: JobCache = context.job_cache  # type: ignore[attr-defined]
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
        cache: JobCache = context.job_cache  # type: ignore[attr-defined]
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
    assert job.canceled is True  # since it failed

    job_client.retry(job)
    job = job_client.find(job)  # load current job state
    assert job.canceled is False

    runner.run_all()  # task will still fail
    job = job_client.find(job)  # load current job state
    assert job.canceled is True  # since it failed

    job_client.retry(job)
    job = job_client.find(job)  # load current job state
    assert job.canceled is False

    cache.group(str(job.id))["succeed"] = b"1"
    runner.run_all()  # now task will succeed
    job = job_client.find(job)  # load current job state
    assert job.state == JobState.COMPLETED


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
