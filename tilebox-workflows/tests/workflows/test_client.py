from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from _tilebox.errors import NotFoundError
from tilebox.datasets.query.time_interval import datetime_to_timestamp
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.workflows.data import (
    Artifact,
    Cluster,
    FilesystemNode,
    ReleaseContent,
    UnboundTaskIdentifier,
    Workflow,
    WorkflowRelease,
)
from tilebox.workflows.v1.workflows_connect import WorkflowsServiceClientSync
from tilebox.workflows.v1.workflows_pb import (
    Cluster as ClusterMessage,
)
from tilebox.workflows.v1.workflows_pb import (
    CreateWorkflowRequest,
    DeleteWorkflowRequest,
    DeployWorkflowReleaseRequest,
    DeployWorkflowReleaseResponse,
    GetWorkflowRequest,
    ListWorkflowsRequest,
    ListWorkflowsResponse,
    UndeployWorkflowReleaseRequest,
    UndeployWorkflowReleaseResponse,
    UnpublishWorkflowReleaseRequest,
    UpdateWorkflowRequest,
)
from tilebox.workflows.v1.workflows_pb import (
    Workflow as WorkflowMessage,
)
from tilebox.workflows.v1.workflows_pb import (
    WorkflowRelease as WorkflowReleaseMessage,
)
from tilebox.workflows.workflows.client import WorkflowClient


class MockWorkflowService:
    """Store workflows in memory for client behavior tests."""

    def __init__(self) -> None:
        self.workflows: dict[str, WorkflowMessage] = {}
        self.unpublished_releases: list[tuple[str, UUID]] = []
        self.deploy_requests: list[DeployWorkflowReleaseRequest] = []
        self.undeploy_requests: list[UndeployWorkflowReleaseRequest] = []
        self.update_requests: list[UpdateWorkflowRequest] = []
        self.create_requests: list[CreateWorkflowRequest] = []

    def create_workflow(self, req: CreateWorkflowRequest) -> WorkflowMessage:
        self.create_requests.append(req)
        slug = req.name.lower().replace(" ", "-")
        workflow = WorkflowMessage(
            id=uuid_to_uuid_message(uuid4()),
            reference=slug,
            name=req.name,
            description=req.description,
            summary=req.summary,
            project_slug=req.project_slug,
            legacy_task_aliases=req.legacy_task_aliases if req.has_field("legacy_task_aliases") else True,
        )
        self.workflows[workflow.reference] = workflow
        return workflow

    def list_workflows(self, req: ListWorkflowsRequest) -> ListWorkflowsResponse:
        _ = req
        return ListWorkflowsResponse(workflows=list(self.workflows.values()))

    def get_workflow(self, req: GetWorkflowRequest) -> WorkflowMessage:
        if req.workflow_reference in self.workflows:
            return self.workflows[req.workflow_reference]
        raise NotFoundError(f"Workflow {req.workflow_reference} not found")

    def update_workflow(self, req: UpdateWorkflowRequest) -> WorkflowMessage:
        self.update_requests.append(req)
        if req.workflow_reference not in self.workflows:
            raise NotFoundError(f"Workflow {req.workflow_reference} not found")

        workflow = WorkflowMessage.from_binary(self.workflows[req.workflow_reference].to_binary())
        if req.has_field("name"):
            workflow.name = req.name
        if req.has_field("description"):
            workflow.description = req.description
        if req.has_field("summary"):
            workflow.summary = req.summary
        self.workflows[workflow.reference] = workflow
        return workflow

    def delete_workflow(self, req: DeleteWorkflowRequest) -> None:
        if req.workflow_reference in self.workflows:
            del self.workflows[req.workflow_reference]
        else:
            raise NotFoundError(f"Workflow {req.workflow_reference} not found")

    def unpublish_workflow_release(self, req: UnpublishWorkflowReleaseRequest) -> None:
        self.unpublished_releases.append((req.workflow_reference, uuid_message_to_uuid(req.release_id)))

    def deploy_workflow_release(self, req: DeployWorkflowReleaseRequest) -> DeployWorkflowReleaseResponse:
        self.deploy_requests.append(req)
        return DeployWorkflowReleaseResponse(
            release=WorkflowReleaseMessage(id=req.release_id),
            clusters=[ClusterMessage(slug=slug, display_name=slug) for slug in req.cluster_slugs],
        )

    def undeploy_workflow_release(self, req: UndeployWorkflowReleaseRequest) -> UndeployWorkflowReleaseResponse:
        self.undeploy_requests.append(req)
        return UndeployWorkflowReleaseResponse(
            release=WorkflowReleaseMessage(id=req.release_id),
            clusters=[ClusterMessage(slug=slug, display_name=slug) for slug in req.cluster_slugs],
        )


def test_create_workflow() -> None:
    mock_service = MockWorkflowService()
    service = MagicMock(spec=WorkflowsServiceClientSync, wraps=mock_service)
    workflow_client = WorkflowClient(service)

    workflow = workflow_client.create("Agentic Workflow", "Short summary", "Description", project_slug="agentic")

    assert workflow.slug == "agentic-workflow"
    assert workflow.name == "Agentic Workflow"
    assert workflow.description == "Description"
    assert workflow.summary == "Short summary"
    assert workflow.id is not None
    assert workflow.reference == workflow.slug
    assert workflow.project_slug == "agentic"
    assert workflow.legacy_task_aliases is False
    request = mock_service.create_requests[-1]
    assert request.has_field("legacy_task_aliases")
    assert request.legacy_task_aliases is False


def test_list_find_and_delete_workflows() -> None:
    mock_service = MockWorkflowService()
    service = MagicMock(spec=WorkflowsServiceClientSync, wraps=mock_service)
    workflow_client = WorkflowClient(service)
    workflow = workflow_client.create("Agentic Workflow", "Short summary")

    assert workflow.description == ""
    assert workflow_client.all() == [workflow]
    assert workflow_client.find(workflow.slug) == workflow

    workflow_client.delete(workflow)

    assert workflow_client.all() == []


def test_update_workflow() -> None:
    mock_service = MockWorkflowService()
    service = MagicMock(spec=WorkflowsServiceClientSync, wraps=mock_service)
    workflow_client = WorkflowClient(service)
    workflow = workflow_client.create("Agentic Workflow", "Short summary", "Description")

    updated_workflow = workflow_client.update(workflow, "Updated Workflow", "Updated summary", "Updated description")

    request = mock_service.update_requests[-1]
    assert request.workflow_reference == workflow.slug
    assert request.has_field("name")
    assert request.has_field("description")
    assert request.name == "Updated Workflow"
    assert request.description == "Updated description"
    assert updated_workflow.name == "Updated Workflow"
    assert updated_workflow.summary == "Updated summary"
    assert updated_workflow.description == "Updated description"


def test_update_workflow_preserves_optional_presence() -> None:
    mock_service = MockWorkflowService()
    service = MagicMock(spec=WorkflowsServiceClientSync, wraps=mock_service)
    workflow_client = WorkflowClient(service)
    workflow = workflow_client.create("Agentic Workflow", description="Description", summary="Short summary")

    unchanged = workflow_client.update(workflow.slug)
    assert unchanged == workflow
    request = mock_service.update_requests[-1]
    assert not request.has_field("name")
    assert not request.has_field("description")
    assert not request.has_field("summary")

    unchanged = workflow_client.update(workflow.slug, name=None, summary=None, description=None)
    assert unchanged == workflow

    updated_workflow = workflow_client.update(workflow.slug, summary=None, description="")
    request = mock_service.update_requests[-1]
    assert not request.has_field("name")
    assert not request.has_field("summary")
    assert request.has_field("description")
    assert request.description == ""
    assert updated_workflow.description == ""
    assert updated_workflow.summary == "Short summary"

    updated_workflow = workflow_client.update(workflow.slug, summary="Updated summary")
    assert updated_workflow.summary == "Updated summary"
    assert updated_workflow.description == ""
    updated_workflow = workflow_client.update(workflow.slug, description="Restored description")
    updated_workflow = workflow_client.update(workflow.slug, summary="", description=None)
    assert updated_workflow.summary == ""
    assert updated_workflow.description == "Restored description"
    assert workflow_client.find(workflow.slug) == updated_workflow


def test_unpublish_release() -> None:
    mock_service = MockWorkflowService()
    service = MagicMock(spec=WorkflowsServiceClientSync, wraps=mock_service)
    workflow_client = WorkflowClient(service)
    release_id = uuid4()

    workflow_client.unpublish_release("agentic-workflow", str(release_id))

    assert mock_service.unpublished_releases == [("agentic-workflow", release_id)]


def test_deploy_release() -> None:
    mock_service = MockWorkflowService()
    service = MagicMock(spec=WorkflowsServiceClientSync, wraps=mock_service)
    workflow_client = WorkflowClient(service)
    release_id = uuid4()

    deployment = workflow_client.deploy_release("agentic-workflow", release_id, clusters=["dev", "prod"])

    request = mock_service.deploy_requests[-1]
    assert request.workflow_reference == "agentic-workflow"
    assert uuid_message_to_uuid(request.release_id) == release_id
    assert list(request.cluster_slugs) == ["dev", "prod"]
    assert deployment.release.id == release_id
    assert [cluster.slug for cluster in deployment.clusters] == ["dev", "prod"]


def test_undeploy_release() -> None:
    mock_service = MockWorkflowService()
    service = MagicMock(spec=WorkflowsServiceClientSync, wraps=mock_service)
    workflow_client = WorkflowClient(service)
    release_id = uuid4()

    deployment = workflow_client.undeploy_release("agentic-workflow", release_id, clusters="dev")

    request = mock_service.undeploy_requests[-1]
    assert request.workflow_reference == "agentic-workflow"
    assert uuid_message_to_uuid(request.release_id) == release_id
    assert list(request.cluster_slugs) == ["dev"]
    assert deployment.release.id == release_id
    assert [cluster.slug for cluster in deployment.clusters] == ["dev"]


def test_workflow_release_data_includes_release_content_and_clusters() -> None:
    release_id = uuid4()
    artifact_id = uuid4()
    created_at = datetime.now(tz=UTC).replace(microsecond=0)
    release = WorkflowRelease(
        id=release_id,
        artifact=Artifact(artifact_id, "a" * 64),
        content=ReleaseContent(
            fingerprint="b" * 64,
            tasks=[UnboundTaskIdentifier("tilebox.com/task/Review", "v1.0")],
            files=[FilesystemNode(".", directory=True, children=[FilesystemNode("main.py")])],
            runner_object_path="my_module.my_runner:runner",
            command_override=["python", "main.py"],
        ),
        created_at=created_at,
        clusters=[],
    )
    workflow = Workflow("agentic-workflow", "Agentic Workflow", "Description", releases=[release])
    cluster = ClusterMessage(
        slug="dev",
        display_name="Dev",
        deployed_releases=[workflow.to_message()],
    )

    restored_release = WorkflowRelease.from_message(
        WorkflowReleaseMessage(
            id=uuid_to_uuid_message(release_id),
            artifact=release.artifact.to_message() if release.artifact else None,
            content=release.content.to_message() if release.content else None,
            created_at=datetime_to_timestamp(created_at),
            clusters=[cluster],
        )
    )

    assert restored_release.id == release_id
    assert restored_release.artifact == release.artifact
    assert restored_release.content == release.content
    assert restored_release.created_at == created_at
    assert restored_release.clusters[0].deployed_workflows == []
    assert Cluster.from_message(cluster).deployed_workflows == [workflow]
