from hypothesis import given

from tests.tasks_data import (
    automations,
    clusters,
    computed_tasks,
    idling_responses,
    jobs,
    progress_bars,
    storage_locations,
    task_identifiers,
    task_leases,
    task_submissions,
    tasks,
)
from tilebox.workflows.data import (
    AutomationPrototype,
    Cluster,
    ComputedTask,
    Idling,
    Job,
    ProgressBar,
    StorageLocation,
    Task,
    TaskIdentifier,
    TaskLease,
    TaskSubmission,
)


@given(task_identifiers())
def test_task_identifiers_to_message_and_back(task_id: TaskIdentifier) -> None:
    assert TaskIdentifier.from_message(task_id.to_message()) == task_id

@given(progress_bars())
def test_progress_bars_to_message_and_back(progress_bar: ProgressBar) -> None:
    assert ProgressBar.from_message(progress_bar.to_message()) == progress_bar

@given(tasks())
def test_tasks_to_message_and_back(task: Task) -> None:
    assert Task.from_message(task.to_message()) == task


@given(idling_responses())
def test_idling_responses_to_message_and_back(idling: Idling) -> None:
    assert Idling.from_message(idling.to_message()) == idling


@given(jobs())
def test_jobs_to_message_and_back(job: Job) -> None:
    assert Job.from_message(job.to_message()) == job


@given(clusters())
def test_cluster_repr(cluster: Cluster) -> None:
    assert cluster.slug in repr(cluster)
    assert cluster.display_name in repr(cluster)


@given(clusters())
def test_clusters_to_message_and_back(cluster: Cluster) -> None:
    assert Cluster.from_message(cluster.to_message()) == cluster


@given(task_submissions())
def test_sub_tasks_to_message_and_back(sub_task: TaskSubmission) -> None:
    assert TaskSubmission.from_message(sub_task.to_message()) == sub_task


@given(computed_tasks())
def test_computed_tasks_to_message_and_back(computed_task: ComputedTask) -> None:
    assert ComputedTask.from_message(computed_task.to_message()) == computed_task


@given(task_leases())
def test_task_leases_to_message_and_back(task_lease: TaskLease) -> None:
    assert TaskLease.from_message(task_lease.to_message()) == task_lease


@given(storage_locations())
def test_buckets_to_message_and_back(storage_location: StorageLocation) -> None:
    assert StorageLocation.from_message(storage_location.to_message()) == storage_location


@given(automations())
def test_automation_to_message_and_back(automation: AutomationPrototype) -> None:
    assert AutomationPrototype.from_message(automation.to_message()) == automation
