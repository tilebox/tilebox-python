from __future__ import annotations

from typing import Any
from uuid import UUID

from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.uuid import must_uuid_to_uuid_message
from tilebox.workflows.data import Workflow, WorkflowRelease, WorkflowReleaseDeployment
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
from tilebox.workflows.workflows.v1.workflows_pb2_grpc import WorkflowsServiceStub


class WorkflowService:
    def __init__(self, channel: Channel | Any) -> None:
        """
        A wrapper around the WorkflowsServiceStub that provides a more pythonic interface and converts protobuf messages
        to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = (
            with_pythonic_errors(WorkflowsServiceStub(channel)) if hasattr(channel, "unary_unary") else channel
        )

    def create(self, name: str, description: str = "") -> Workflow:
        request = CreateWorkflowRequest(name=name, description=description)
        return Workflow.from_message(self.service.CreateWorkflow(request))

    def list_all(self) -> list[Workflow]:
        request = ListWorkflowsRequest()
        response: ListWorkflowsResponse = self.service.ListWorkflows(request)
        return [Workflow.from_message(workflow) for workflow in response.workflows]

    def get_by_slug(self, workflow_slug: str) -> Workflow:
        request = GetWorkflowRequest(workflow_slug=workflow_slug)
        return Workflow.from_message(self.service.GetWorkflow(request))

    def update(self, workflow_slug: str, name: str | None = None, description: str | None = None) -> Workflow:
        request = UpdateWorkflowRequest(workflow_slug=workflow_slug, name=name, description=description)
        return Workflow.from_message(self.service.UpdateWorkflow(request))

    def delete(self, workflow_slug: str) -> None:
        request = DeleteWorkflowRequest(workflow_slug=workflow_slug)
        self.service.DeleteWorkflow(request)

    def unpublish_release(self, workflow_slug: str, release_id: UUID) -> None:
        request = UnpublishWorkflowReleaseRequest(
            workflow_slug=workflow_slug,
            release_id=must_uuid_to_uuid_message(release_id),
        )
        self.service.UnpublishWorkflowRelease(request)

    def deploy_release(
        self,
        workflow_slug: str,
        release_id: UUID,
        cluster_slugs: list[str] | None = None,
    ) -> WorkflowReleaseDeployment:
        request = DeployWorkflowReleaseRequest(
            workflow_slug=workflow_slug,
            release_id=must_uuid_to_uuid_message(release_id),
            cluster_slugs=cluster_slugs or [],
        )
        response: DeployWorkflowReleaseResponse = self.service.DeployWorkflowRelease(request)
        return WorkflowReleaseDeployment.from_deploy_message(response)

    def undeploy_release(
        self,
        workflow_slug: str,
        release_id: UUID,
        cluster_slugs: list[str] | None = None,
    ) -> WorkflowReleaseDeployment:
        request = UndeployWorkflowReleaseRequest(
            workflow_slug=workflow_slug,
            release_id=must_uuid_to_uuid_message(release_id),
            cluster_slugs=cluster_slugs or [],
        )
        response: UndeployWorkflowReleaseResponse = self.service.UndeployWorkflowRelease(request)
        return WorkflowReleaseDeployment.from_undeploy_message(response)


def release_id(release_or_id: WorkflowRelease | UUID | str) -> UUID:
    if isinstance(release_or_id, WorkflowRelease):
        return release_or_id.id
    if isinstance(release_or_id, str):
        return UUID(release_or_id)
    return release_or_id
