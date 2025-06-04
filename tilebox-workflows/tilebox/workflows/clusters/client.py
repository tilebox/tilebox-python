from typing import TypeAlias

from tilebox.workflows.clusters.service import ClusterService
from tilebox.workflows.data import Cluster

ClusterSlugLike: TypeAlias = Cluster | str


class ClusterClient:
    def __init__(self, service: ClusterService) -> None:
        """Create a new cluster client.

        Args:
            service: The service to use for cluster operations.
        """
        self._service = service

    def create(self, name: str) -> Cluster:
        """Create a new cluster with the given name.

        A unique cluster slug will be generated for the cluster.

        Args:
            name: The  name of the cluster to create.

        Returns:
            Cluster: The created cluster.
        """
        return self._service.create(name)

    def all(self) -> list[Cluster]:
        """List all available clusters.

        Returns:
            All available clusters.
        """
        return self._service.list()

    def find(self, cluster_or_slug: ClusterSlugLike) -> Cluster:
        """Find a cluster by slug.

        Args:
            cluster_slug: The slug of the cluster to find.

        Returns:
            The cluster for the given cluster_slug.
        """
        return self._service.get_by_slug(to_cluster_slug(cluster_or_slug))

    def delete(self, cluster_or_slug: ClusterSlugLike) -> None:
        """Delete a cluster by slug.

        Args:
            cluster_slug: The slug of the cluster to delete.
        """
        self._service.delete(to_cluster_slug(cluster_or_slug))


def to_cluster_slug(cluster: Cluster | str) -> str:
    return cluster.slug if isinstance(cluster, Cluster) else cluster
