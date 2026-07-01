from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from _tilebox.grpc.error import NotFoundError
from tilebox.datasets.query.time_interval import datetime_to_timestamp
from tilebox.datasets.uuid import uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.workflows.data import (
    Artifact,
    Cluster,
    FilesystemNode,
    ReleaseContent,
    TaskIdentifier,
    Workflow,
    WorkflowRelease,
)
from tilebox.workflows.workflows.client import WorkflowClient
from tilebox.workflows.workflows.service import WorkflowService
from tilebox.workflows.workflows.v1.workflows_pb2 import (
    Cluster as ClusterMessage,
)
from tilebox.workflows.workflows.v1.workflows_pb2 import (
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
from tilebox.workflows.workflows.v1.workflows_pb2 import (
    Workflow as WorkflowMessage,
)
from tilebox.workflows.workflows.v1.workflows_pb2 import (
    WorkflowRelease as WorkflowReleaseMessage,
)
from tilebox.workflows.workflows.v1.workflows_pb2_grpc import WorkflowsServiceStub


class MockWorkflowService(WorkflowsServiceStub):
    """A mock implementation of the gRPC workflow service, that stores workflows in memory as a dict."""

    def __init__(self) -> None:
        self.workflows: dict[str, WorkflowMessage] = {}
        self.unpublished_releases: list[tuple[str, UUID]] = []
        self.deploy_requests: list[DeployWorkflowReleaseRequest] = []
        self.undeploy_requests: list[UndeployWorkflowReleaseRequest] = []
        self.update_requests: list[UpdateWorkflowRequest] = []

    def CreateWorkflow(self, req: CreateWorkflowRequest) -> WorkflowMessage:  # noqa: N802
        slug = req.name.lower().replace(" ", "-")
        workflow = WorkflowMessage(slug=slug, name=req.name, description=req.description)
        self.workflows[workflow.slug] = workflow
        return workflow

    def ListWorkflows(self, req: ListWorkflowsRequest) -> ListWorkflowsResponse:  # noqa: N802
        _ = req
        return ListWorkflowsResponse(workflows=list(self.workflows.values()))

    def GetWorkflow(self, req: GetWorkflowRequest) -> WorkflowMessage:  # noqa: N802
        if req.workflow_slug in self.workflows:
            return self.workflows[req.workflow_slug]
        raise NotFoundError(f"Workflow {req.workflow_slug} not found")

    def UpdateWorkflow(self, req: UpdateWorkflowRequest) -> WorkflowMessage:  # noqa: N802
        self.update_requests.append(req)
        if req.workflow_slug not in self.workflows:
            raise NotFoundError(f"Workflow {req.workflow_slug} not found")

        workflow = WorkflowMessage.FromString(self.workflows[req.workflow_slug].SerializeToString())
        if req.HasField("name"):
            workflow.name = req.name
        if req.HasField("description"):
            workflow.description = req.description
        self.workflows[workflow.slug] = workflow
        return workflow

    def DeleteWorkflow(self, req: DeleteWorkflowRequest) -> None:  # noqa: N802
        if req.workflow_slug in self.workflows:
            del self.workflows[req.workflow_slug]
        else:
            raise NotFoundError(f"Workflow {req.workflow_slug} not found")

    def UnpublishWorkflowRelease(self, req: UnpublishWorkflowReleaseRequest) -> None:  # noqa: N802
        self.unpublished_releases.append((req.workflow_slug, uuid_message_to_uuid(req.release_id)))

    def DeployWorkflowRelease(self, req: DeployWorkflowReleaseRequest) -> DeployWorkflowReleaseResponse:  # noqa: N802
        self.deploy_requests.append(req)
        return DeployWorkflowReleaseResponse(
            release=WorkflowReleaseMessage(id=req.release_id),
            clusters=[ClusterMessage(slug=slug, display_name=slug) for slug in req.cluster_slugs],
        )

    def UndeployWorkflowRelease(self, req: UndeployWorkflowReleaseRequest) -> UndeployWorkflowReleaseResponse:  # noqa: N802
        self.undeploy_requests.append(req)
        return UndeployWorkflowReleaseResponse(
            release=WorkflowReleaseMessage(id=req.release_id),
            clusters=[ClusterMessage(slug=slug, display_name=slug) for slug in req.cluster_slugs],
        )


def test_create_workflow() -> None:
    service = WorkflowService(MagicMock())
    service.service = MockWorkflowService()
    workflow_client = WorkflowClient(service)

    workflow = workflow_client.create("Agentic Workflow", description="Description")

    assert workflow.slug == "agentic-workflow"
    assert workflow.name == "Agentic Workflow"
    assert workflow.description == "Description"


def test_list_find_and_delete_workflows() -> None:
    service = WorkflowService(MagicMock())
    mock_service = MockWorkflowService()
    service.service = mock_service
    workflow_client = WorkflowClient(service)
    workflow = workflow_client.create("Agentic Workflow")

    assert workflow_client.all() == [workflow]
    assert workflow_client.find(workflow.slug) == workflow

    workflow_client.delete(workflow)

    assert workflow_client.all() == []


def test_update_workflow() -> None:
    service = WorkflowService(MagicMock())
    mock_service = MockWorkflowService()
    service.service = mock_service
    workflow_client = WorkflowClient(service)
    workflow = workflow_client.create("Agentic Workflow", description="Description")

    updated_workflow = workflow_client.update(workflow, name="Updated Workflow", description="Updated description")

    request = mock_service.update_requests[-1]
    assert request.workflow_slug == workflow.slug
    assert request.HasField("name")
    assert request.HasField("description")
    assert request.name == "Updated Workflow"
    assert request.description == "Updated description"
    assert updated_workflow.name == "Updated Workflow"
    assert updated_workflow.description == "Updated description"


def test_update_workflow_preserves_optional_presence() -> None:
    service = WorkflowService(MagicMock())
    mock_service = MockWorkflowService()
    service.service = mock_service
    workflow_client = WorkflowClient(service)
    workflow = workflow_client.create("Agentic Workflow", description="Description")

    workflow_client.update(workflow.slug)
    request = mock_service.update_requests[-1]
    assert not request.HasField("name")
    assert not request.HasField("description")

    updated_workflow = workflow_client.update(workflow.slug, description="")
    request = mock_service.update_requests[-1]
    assert not request.HasField("name")
    assert request.HasField("description")
    assert request.description == ""
    assert updated_workflow.description == ""


def test_unpublish_release() -> None:
    service = WorkflowService(MagicMock())
    mock_service = MockWorkflowService()
    service.service = mock_service
    workflow_client = WorkflowClient(service)
    release_id = uuid4()

    workflow_client.unpublish_release("agentic-workflow", str(release_id))

    assert mock_service.unpublished_releases == [("agentic-workflow", release_id)]


def test_deploy_release() -> None:
    service = WorkflowService(MagicMock())
    mock_service = MockWorkflowService()
    service.service = mock_service
    workflow_client = WorkflowClient(service)
    release_id = uuid4()

    deployment = workflow_client.deploy_release("agentic-workflow", release_id, clusters=["dev", "prod"])

    request = mock_service.deploy_requests[-1]
    assert request.workflow_slug == "agentic-workflow"
    assert uuid_message_to_uuid(request.release_id) == release_id
    assert list(request.cluster_slugs) == ["dev", "prod"]
    assert deployment.release.id == release_id
    assert [cluster.slug for cluster in deployment.clusters] == ["dev", "prod"]


def test_undeploy_release() -> None:
    service = WorkflowService(MagicMock())
    mock_service = MockWorkflowService()
    service.service = mock_service
    workflow_client = WorkflowClient(service)
    release_id = uuid4()

    deployment = workflow_client.undeploy_release("agentic-workflow", release_id, clusters="dev")

    request = mock_service.undeploy_requests[-1]
    assert request.workflow_slug == "agentic-workflow"
    assert uuid_message_to_uuid(request.release_id) == release_id
    assert list(request.cluster_slugs) == ["dev"]
    assert deployment.release.id == release_id
    assert [cluster.slug for cluster in deployment.clusters] == ["dev"]


def test_workflow_release_data_includes_release_content_and_clusters() -> None:
    release_id = uuid4()
    artifact_id = uuid4()
    created_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    release = WorkflowRelease(
        id=release_id,
        artifact=Artifact(artifact_id, "a" * 64),
        content=ReleaseContent(
            fingerprint="b" * 64,
            tasks=[TaskIdentifier("tilebox.com/task/Review", "v1.0")],
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
