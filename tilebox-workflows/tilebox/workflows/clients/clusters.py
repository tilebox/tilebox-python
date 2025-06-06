from grpc.aio import Channel

from _tilebox.grpc.aio.syncify import Syncifiable
from tilebox.workflows.data import (
    Cluster,
)
from tilebox.workflows.workflowsv1.core_pb2 import Cluster as ClusterMessage
from tilebox.workflows.workflowsv1.workflows_pb2 import (
    CreateClusterRequest,
    DeleteClusterRequest,
    GetClusterRequest,
    ListClustersRequest,
    ListClustersResponse,
)
from tilebox.workflows.workflowsv1.workflows_pb2_grpc import WorkflowsServiceStub


class ClusterService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the WorkflowsServiceStub that provides a more pythonic interface and converts the protobuf
        messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = WorkflowsServiceStub(channel)

    async def create(self, cluster_name: str) -> Cluster:
        """Create a new cluster.

        Args:
            cluster_name: The name of the cluster to create.

        Returns:
            The created cluster.
        """
        request = CreateClusterRequest(name=cluster_name)
        response: ClusterMessage = await self.service.CreateCluster(request)
        return Cluster.from_message(response)

    async def get_by_slug(self, cluster_slug: str) -> Cluster:
        """Get cluster details by its slug.

        Args:
            cluster_slug: The cluster to get details for.

        Returns:
            The cluster details.
        """
        request = GetClusterRequest(cluster_slug=cluster_slug)
        response: ClusterMessage = await self.service.GetCluster(request)
        return Cluster.from_message(response)

    async def delete(self, cluster_slug: str) -> None:
        """Delete a cluster.

        Args:
            cluster_slug: The cluster to delete.
        """
        request = DeleteClusterRequest(cluster_slug=cluster_slug)
        await self.service.DeleteCluster(request)

    async def list(self) -> list[Cluster]:
        """List all clusters.

        Returns:
            A list of clusters.
        """
        request = ListClustersRequest()
        response: ListClustersResponse = await self.service.ListClusters(request)
        return [Cluster.from_message(cluster) for cluster in response.clusters]


class ClusterClient(Syncifiable):
    def __init__(self, service: ClusterService) -> None:
        """Create a new cluster client.

        Args:
            service: The service to use for cluster operations.
        """
        self._service = service

    async def create(self, name: str) -> Cluster:
        """Create a new cluster with the given name.

        A unique cluster slug will be generated for the cluster.

        Args:
            name: The  name of the cluster to create.

        Returns:
            Cluster: The created cluster.
        """
        return await self._service.create(name)

    async def all(self) -> list[Cluster]:
        """List all available clusters.

        Returns:
            All available clusters.
        """
        return await self._service.list()

    async def find(self, cluster_slug: str) -> Cluster:
        """Find a cluster by slug.

        Args:
            cluster_slug: The slug of the cluster to find.

        Returns:
            The cluster for the given cluster_slug.
        """
        return await self._service.get_by_slug(cluster_slug)

    async def delete(self, cluster_slug: str) -> None:
        """Delete a cluster by slug.

        Args:
            cluster_slug: The slug of the cluster to delete.
        """
        await self._service.delete(cluster_slug)


def cluster_slug(cluster: Cluster | str) -> str:
    return cluster.slug if isinstance(cluster, Cluster) else cluster
