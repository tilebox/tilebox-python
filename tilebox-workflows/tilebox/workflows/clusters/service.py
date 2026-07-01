from typing import Any

from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.workflows.data import (
    Cluster,
)
from tilebox.workflows.workflows.v1.workflows_pb2 import (
    CreateClusterRequest,
    DeleteClusterRequest,
    GetClusterRequest,
    ListClustersRequest,
    ListClustersResponse,
    UpdateClusterRequest,
)
from tilebox.workflows.workflows.v1.workflows_pb2_grpc import WorkflowsServiceStub


class ClusterService:
    def __init__(self, channel: Channel | Any) -> None:
        """
        A wrapper around the WorkflowsServiceStub that provides a more pythonic interface and converts the protobuf
        messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = (
            with_pythonic_errors(WorkflowsServiceStub(channel)) if hasattr(channel, "unary_unary") else channel
        )

    def create(self, cluster_name: str, description: str | None = None, slug: str | None = None) -> Cluster:
        request = CreateClusterRequest(name=cluster_name, description=description, slug=slug or "")
        return Cluster.from_message(self.service.CreateCluster(request))

    def update(self, cluster_slug: str, name: str | None = None, description: str | None = None) -> Cluster:
        request = UpdateClusterRequest(cluster_slug=cluster_slug, name=name, description=description)
        return Cluster.from_message(self.service.UpdateCluster(request))

    def get_by_slug(self, cluster_slug: str) -> Cluster:
        request = GetClusterRequest(cluster_slug=cluster_slug)
        return Cluster.from_message(self.service.GetCluster(request))

    def delete(self, cluster_slug: str) -> None:
        request = DeleteClusterRequest(cluster_slug=cluster_slug)
        self.service.DeleteCluster(request)

    def list(self) -> list[Cluster]:
        request = ListClustersRequest()
        response: ListClustersResponse = self.service.ListClusters(request)
        return [Cluster.from_message(cluster) for cluster in response.clusters]
