from typing import TypeAlias
from uuid import UUID

from tilebox.workflows.clusters.client import ClusterSlugLike, to_cluster_slug
from tilebox.workflows.data import Workflow, WorkflowRelease, WorkflowReleaseDeployment
from tilebox.workflows.workflows.service import WorkflowService, release_id

WorkflowSlugLike: TypeAlias = Workflow | str
WorkflowReleaseLike: TypeAlias = WorkflowRelease | UUID | str


class WorkflowClient:
    def __init__(self, service: WorkflowService) -> None:
        """Create a new workflow client.

        Args:
            service: The service to use for workflow operations.
        """
        self._service = service

    def create(self, name: str, description: str = "") -> Workflow:
        """Create a new workflow with the given name.

        Args:
            name: The name of the workflow to create.
            description: The description of the workflow to create.

        Returns:
            The created workflow.
        """
        return self._service.create(name, description)

    def all(self) -> list[Workflow]:
        """List all available workflows.

        Returns:
            All available workflows.
        """
        return self._service.list_all()

    def find(self, workflow_or_slug: WorkflowSlugLike) -> Workflow:
        """Find a workflow by slug.

        Args:
            workflow_or_slug: The workflow or slug of the workflow to find.

        Returns:
            The workflow for the given workflow slug.
        """
        return self._service.get_by_slug(to_workflow_slug(workflow_or_slug))

    def update(
        self,
        workflow_or_slug: WorkflowSlugLike,
        name: str | None = None,
        description: str | None = None,
    ) -> Workflow:
        """Update a workflow by slug.

        Args:
            workflow_or_slug: The workflow or slug of the workflow to update.
            name: The new display name for the workflow. If not provided, the name is left unchanged.
            description: The new description for the workflow. If not provided, the description is left unchanged.

        Returns:
            The updated workflow.
        """
        return self._service.update(to_workflow_slug(workflow_or_slug), name, description)

    def delete(self, workflow_or_slug: WorkflowSlugLike) -> None:
        """Delete a workflow by slug.

        Args:
            workflow_or_slug: The workflow or slug of the workflow to delete.
        """
        self._service.delete(to_workflow_slug(workflow_or_slug))

    def unpublish_release(self, workflow_or_slug: WorkflowSlugLike, release_or_id: WorkflowReleaseLike) -> None:
        """Unpublish a workflow release.

        Args:
            workflow_or_slug: The workflow or slug containing the release to unpublish.
            release_or_id: The workflow release or id of the release to unpublish.
        """
        self._service.unpublish_release(to_workflow_slug(workflow_or_slug), release_id(release_or_id))

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
        return self._service.deploy_release(
            to_workflow_slug(workflow_or_slug),
            release_id(release_or_id),
            _to_cluster_slugs(clusters),
        )

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
        return self._service.undeploy_release(
            to_workflow_slug(workflow_or_slug),
            release_id(release_or_id),
            _to_cluster_slugs(clusters),
        )


def to_workflow_slug(workflow: WorkflowSlugLike) -> str:
    return workflow.slug if isinstance(workflow, Workflow) else workflow


def _to_cluster_slugs(clusters: ClusterSlugLike | list[ClusterSlugLike] | None) -> list[str]:
    clusters = clusters or []
    if isinstance(clusters, ClusterSlugLike):
        clusters = [clusters]
    return [to_cluster_slug(cluster) for cluster in clusters]
