from typing import TypeAlias

from tilebox.workflows.data import Cluster
from tilebox.workflows.v1.workflows_connect import WorkflowsServiceClientSync
from tilebox.workflows.v1.workflows_pb import (
    CreateClusterRequest,
    DeleteClusterRequest,
    GetClusterRequest,
    ListClustersRequest,
    UpdateClusterRequest,
)

ClusterSlugLike: TypeAlias = Cluster | str


class ClusterClient:
    def __init__(self, service: WorkflowsServiceClientSync) -> None:
        """Create a new cluster client.

        Args:
            service: The service to use for cluster operations.
        """
        self._service = service

    def create(self, name: str, description: str | None = None, slug: str | None = None) -> Cluster:
        """Create a new cluster with the given name.

        If no slug is provided, a unique cluster slug will be generated for the cluster.

        Args:
            name: The  name of the cluster to create.
            description: The description of the cluster to create.
            slug: The slug to use for the cluster.

        Returns:
            Cluster: The created cluster.
        """
        request = CreateClusterRequest(name=name, description=description or "", slug=slug or "")
        return Cluster.from_message(self._service.create_cluster(request))

    def update(
        self,
        cluster_or_slug: ClusterSlugLike,
        name: str | None = None,
        description: str | None = None,
    ) -> Cluster:
        """Update a cluster by slug.

        Args:
            cluster_or_slug: The cluster or slug of the cluster to update.
            name: The new display name for the cluster. If not provided, the name is left unchanged.
            description: The new description for the cluster. If not provided, the description is left unchanged.

        Returns:
            The updated cluster.
        """
        request = UpdateClusterRequest(
            cluster_slug=to_cluster_slug(cluster_or_slug), name=name, description=description
        )
        return Cluster.from_message(self._service.update_cluster(request))

    def all(self) -> list[Cluster]:
        """List all available clusters.

        Returns:
            All available clusters.
        """
        response = self._service.list_clusters(ListClustersRequest())
        return [Cluster.from_message(cluster) for cluster in response.clusters]

    def find(self, cluster_or_slug: ClusterSlugLike) -> Cluster:
        """Find a cluster by slug.

        Args:
            cluster_slug: The slug of the cluster to find.

        Returns:
            The cluster for the given cluster_slug.
        """
        return Cluster.from_message(
            self._service.get_cluster(GetClusterRequest(cluster_slug=to_cluster_slug(cluster_or_slug)))
        )

    def delete(self, cluster_or_slug: ClusterSlugLike) -> None:
        """Delete a cluster by slug.

        Args:
            cluster_slug: The slug of the cluster to delete.
        """
        self._service.delete_cluster(DeleteClusterRequest(cluster_slug=to_cluster_slug(cluster_or_slug)))


def to_cluster_slug(cluster: Cluster | str) -> str:
    return cluster.slug if isinstance(cluster, Cluster) else cluster
