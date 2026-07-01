from hypothesis import given

from tests.tasks_data import (
    artifacts,
    automations,
    clusters,
    computed_tasks,
    execution_stats,
    idling_responses,
    jobs,
    progress_indicators,
    query_filters,
    release_contents,
    release_filesystem_nodes,
    single_task_submissions,
    storage_locations,
    task_identifiers,
    task_leases,
    task_submission_groups,
    task_submissions,
    tasks,
    workflow_releases,
    workflows,
)
from tilebox.workflows.data import (
    Artifact,
    AutomationPrototype,
    Cluster,
    ComputedTask,
    ExecutionStats,
    FilesystemNode,
    Idling,
    Job,
    ProgressIndicator,
    QueryFilters,
    ReleaseContent,
    SingleTaskSubmission,
    StorageLocation,
    Task,
    TaskIdentifier,
    TaskLease,
    TaskSubmissionGroup,
    TaskSubmissions,
    Workflow,
    WorkflowRelease,
)


@given(task_identifiers())
def test_task_identifiers_to_message_and_back(task_id: TaskIdentifier) -> None:
    assert TaskIdentifier.from_message(task_id.to_message()) == task_id


@given(progress_indicators())
def test_progress_indicators_to_message_and_back(progress_indicator: ProgressIndicator) -> None:
    assert ProgressIndicator.from_message(progress_indicator.to_message()) == progress_indicator


@given(tasks())
def test_tasks_to_message_and_back(task: Task) -> None:
    assert Task.from_message(task.to_message()) == task


@given(idling_responses())
def test_idling_responses_to_message_and_back(idling: Idling) -> None:
    assert Idling.from_message(idling.to_message()) == idling


@given(execution_stats())
def test_execution_stats_to_message_and_back(execution_stats: ExecutionStats) -> None:
    assert ExecutionStats.from_message(execution_stats.to_message()) == execution_stats


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


@given(artifacts())
def test_artifacts_to_message_and_back(artifact: Artifact) -> None:
    assert Artifact.from_message(artifact.to_message()) == artifact


@given(release_filesystem_nodes())
def test_release_filesystem_nodes_to_message_and_back(node: FilesystemNode) -> None:
    assert FilesystemNode.from_message(node.to_message()) == node


@given(release_contents())
def test_release_contents_to_message_and_back(content: ReleaseContent) -> None:
    assert ReleaseContent.from_message(content.to_message()) == content


@given(workflow_releases())
def test_workflow_releases_to_message_and_back(release: WorkflowRelease) -> None:
    assert WorkflowRelease.from_message(release.to_message()) == release


@given(workflows())
def test_workflows_to_message_and_back(workflow: Workflow) -> None:
    assert Workflow.from_message(workflow.to_message()) == workflow


@given(task_submissions())
def test_task_submissions_to_message_and_back(sub_task: TaskSubmissions) -> None:
    assert TaskSubmissions.from_message(sub_task.to_message()) == sub_task


@given(task_submission_groups())
def test_task_submission_groups_to_message_and_back(sub_task: TaskSubmissionGroup) -> None:
    assert TaskSubmissionGroup.from_message(sub_task.to_message()) == sub_task


@given(single_task_submissions())
def test_single_task_submissions_to_message_and_back(sub_task: SingleTaskSubmission) -> None:
    assert SingleTaskSubmission.from_message(sub_task.to_message()) == sub_task


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


@given(query_filters())
def test_query_filters_to_message_and_back(filters: QueryFilters) -> None:
    assert QueryFilters.from_message(filters.to_message()) == filters
