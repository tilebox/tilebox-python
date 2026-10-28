from typing import TypeAlias
from uuid import UUID

from _tilebox.uuid import must_uuid_to_uuid_message
from tilebox.workflows.clusters.client import ClusterSlugLike, to_cluster_slug
from tilebox.workflows.data import Workflow, WorkflowRelease, WorkflowReleaseDeployment
from tilebox.workflows.v1.workflows_connect import WorkflowsServiceClientSync
from tilebox.workflows.v1.workflows_pb import (
    CreateWorkflowRequest,
    DeleteWorkflowRequest,
    DeployWorkflowReleaseRequest,
    GetWorkflowRequest,
    ListWorkflowsRequest,
    UndeployWorkflowReleaseRequest,
    UnpublishWorkflowReleaseRequest,
    UpdateWorkflowRequest,
)

WorkflowReferenceLike: TypeAlias = Workflow | str
WorkflowSlugLike: TypeAlias = WorkflowReferenceLike
WorkflowReleaseLike: TypeAlias = WorkflowRelease | UUID | str


class WorkflowClient:
    def __init__(self, service: WorkflowsServiceClientSync) -> None:
        """Create a new workflow client.

        Args:
            service: The service to use for workflow operations.
        """
        self._service = service

    def create(
        self,
        name: str,
        summary: str,
        description: str = "",
        *,
        project_slug: str = "",
    ) -> Workflow:
        """Create a new scoped-only workflow with the given name.

        Args:
            name: The name of the workflow to create.
            summary: The short summary of the workflow to create.
            description: The description of the workflow to create. Defaults to an empty string.
            project_slug: Portable project name, not a remote workflow reference.

        Returns:
            The created workflow.
        """
        return Workflow.from_message(
            self._service.create_workflow(
                CreateWorkflowRequest(
                    name=name,
                    summary=summary,
                    description=description,
                    project_slug=project_slug,
                    legacy_task_aliases=False,
                )
            )
        )

    def all(self) -> list[Workflow]:
        """List all available workflows.

        Returns:
            All available workflows.
        """
        response = self._service.list_workflows(ListWorkflowsRequest())
        return [Workflow.from_message(workflow) for workflow in response.workflows]

    def find(self, workflow_or_slug: WorkflowSlugLike) -> Workflow:
        """Find a workflow by slug.

        Args:
            workflow_or_slug: The workflow or slug of the workflow to find.

        Returns:
            The workflow for the given workflow slug.
        """
        return Workflow.from_message(
            self._service.get_workflow(GetWorkflowRequest(workflow_reference=to_workflow_slug(workflow_or_slug)))
        )

    def update(
        self,
        workflow_or_slug: WorkflowSlugLike,
        name: str | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> Workflow:
        """Update a workflow by slug.

        Args:
            workflow_or_slug: The workflow or slug of the workflow to update.
            name: The new display name for the workflow. If not provided, the name is left unchanged.
            summary: The new short summary. ``None`` leaves it unchanged; ``""`` clears it.
            description: The new description. ``None`` leaves it unchanged; ``""`` clears it.

        Returns:
            The updated workflow.
        """
        request = UpdateWorkflowRequest(
            workflow_reference=to_workflow_slug(workflow_or_slug), name=name, summary=summary, description=description
        )
        return Workflow.from_message(self._service.update_workflow(request))

    def delete(self, workflow_or_slug: WorkflowSlugLike) -> None:
        """Delete a workflow by slug.

        Args:
            workflow_or_slug: The workflow or slug of the workflow to delete.
        """
        self._service.delete_workflow(DeleteWorkflowRequest(workflow_reference=to_workflow_slug(workflow_or_slug)))

    def unpublish_release(self, workflow_or_slug: WorkflowSlugLike, release_or_id: WorkflowReleaseLike) -> None:
        """Unpublish a workflow release.

        Args:
            workflow_or_slug: The workflow or slug containing the release to unpublish.
            release_or_id: The workflow release or id of the release to unpublish.
        """
        self._service.unpublish_workflow_release(
            UnpublishWorkflowReleaseRequest(
                workflow_reference=to_workflow_slug(workflow_or_slug),
                release_id=must_uuid_to_uuid_message(release_id(release_or_id)),
            )
        )

    def deploy_release(
        self,
        workflow_or_slug: WorkflowSlugLike,
        release_or_id: WorkflowReleaseLike,
        clusters: ClusterSlugLike | list[ClusterSlugLike] | None = None,
    ) -> WorkflowReleaseDeployment:
        """Deploy a workflow release to clusters.

        Args:
            workflow_or_slug: The workflow or slug containing the release to deploy.
            release_or_id: The workflow release or id of the release to deploy.
            clusters: The cluster or clusters to deploy the release to. If omitted, the API default cluster is used.

        Returns:
            The deployed release and affected clusters.
        """
        request = DeployWorkflowReleaseRequest(
            workflow_reference=to_workflow_slug(workflow_or_slug),
            release_id=must_uuid_to_uuid_message(release_id(release_or_id)),
            cluster_slugs=_to_cluster_slugs(clusters),
        )
        return WorkflowReleaseDeployment.from_deploy_message(self._service.deploy_workflow_release(request))

    def undeploy_release(
        self,
        workflow_or_slug: WorkflowSlugLike,
        release_or_id: WorkflowReleaseLike,
        clusters: ClusterSlugLike | list[ClusterSlugLike] | None = None,
    ) -> WorkflowReleaseDeployment:
        """Undeploy a workflow release from clusters.

        Args:
            workflow_or_slug: The workflow or slug containing the release to undeploy.
            release_or_id: The workflow release or id of the release to undeploy.
            clusters: The cluster or clusters to undeploy the release from. If omitted, the API default cluster is used.

        Returns:
            The undeployed release and affected clusters.
        """
        request = UndeployWorkflowReleaseRequest(
            workflow_reference=to_workflow_slug(workflow_or_slug),
            release_id=must_uuid_to_uuid_message(release_id(release_or_id)),
            cluster_slugs=_to_cluster_slugs(clusters),
        )
        return WorkflowReleaseDeployment.from_undeploy_message(self._service.undeploy_workflow_release(request))


def to_workflow_slug(workflow: WorkflowSlugLike) -> str:
    return workflow.reference if isinstance(workflow, Workflow) else workflow


def resolve_workflow_id(
    workflow: WorkflowReferenceLike | None, service: WorkflowsServiceClientSync | None
) -> UUID | None:
    if workflow is None:
        return None
    if isinstance(workflow, str):
        if not workflow:
            raise ValueError("A workflow reference is required")
        if service is None:
            raise ValueError("A workflow service is required to resolve workflow references")
        workflow = Workflow.from_message(service.get_workflow(GetWorkflowRequest(workflow_reference=workflow)))
    if workflow.id is None or workflow.id.int == 0:
        raise ValueError("Workflow must have a non-Nil ID to scope tasks")
    return workflow.id


def release_id(release_or_id: WorkflowReleaseLike) -> UUID:
    if isinstance(release_or_id, WorkflowRelease):
        return release_or_id.id
    return UUID(release_or_id) if isinstance(release_or_id, str) else release_or_id


def _to_cluster_slugs(clusters: ClusterSlugLike | list[ClusterSlugLike] | None) -> list[str]:
    clusters = clusters or []
    if isinstance(clusters, ClusterSlugLike):
        clusters = [clusters]
    return [to_cluster_slug(cluster) for cluster in clusters]
