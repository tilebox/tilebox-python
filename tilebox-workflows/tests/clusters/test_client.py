from unittest.mock import MagicMock
from uuid import uuid4

from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, rule
from tests.tasks_data import clusters

from _tilebox.grpc.error import NotFoundError
from tilebox.workflows.clusters.client import ClusterClient
from tilebox.workflows.clusters.service import ClusterService
from tilebox.workflows.data import (
    Cluster,
)
from tilebox.workflows.workflows.v1.workflows_pb2 import (
    Cluster as ClusterMessage,
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


class MockClusterService(WorkflowsServiceStub):
    """A mock implementation of the gRPC cluster service, that stores clusters in memory as a dict."""

    def __init__(self) -> None:
        self.clusters: dict[str, ClusterMessage] = {}

    def CreateCluster(self, req: CreateClusterRequest) -> ClusterMessage:  # noqa: N802
        cluster = ClusterMessage(slug=req.slug or str(uuid4()), display_name=req.name, description=req.description)
        self.clusters[cluster.slug] = cluster
        return cluster

    def UpdateCluster(self, req: UpdateClusterRequest) -> ClusterMessage:  # noqa: N802
        if req.cluster_slug not in self.clusters:
            raise NotFoundError(f"Cluster {req.cluster_slug} not found")

        cluster = ClusterMessage.FromString(self.clusters[req.cluster_slug].SerializeToString())
        if req.HasField("name"):
            cluster.display_name = req.name
        if req.HasField("description"):
            cluster.description = req.description
        self.clusters[cluster.slug] = cluster
        return cluster

    def GetCluster(self, req: GetClusterRequest) -> ClusterMessage:  # noqa: N802
        if req.cluster_slug in self.clusters:
            return self.clusters[req.cluster_slug]
        raise NotFoundError(f"Cluster {req.cluster_slug} not found")

    def DeleteCluster(self, req: DeleteClusterRequest) -> None:  # noqa: N802
        if req.cluster_slug in self.clusters:
            del self.clusters[req.cluster_slug]
        else:
            raise NotFoundError(f"Cluster {req.cluster_slug} not found")

    def ListClusters(self, req: ListClustersRequest) -> ListClustersResponse:  # noqa: N802
        _ = req
        return ListClustersResponse(clusters=list(self.clusters.values()))


def test_create_cluster_can_use_custom_slug() -> None:
    service = ClusterService(MagicMock())
    service.service = MockClusterService()
    cluster_client = ClusterClient(service)

    cluster = cluster_client.create("Test Cluster", description="Test description", slug="test-cluster")

    assert cluster.slug == "test-cluster"
    assert cluster.display_name == "Test Cluster"
    assert cluster.description == "Test description"


class ClusterCRUDOperations(RuleBasedStateMachine):
    """
    A state machine that tests the CRUD operations of the Clusters client.

    The rules defined here will be executed in random order by Hypothesis, and each rule can be called any number of
    times. The state of the state machine is defined by the bundles, which are collections of objects that can be
    inserted into the state machine by the rules. Rules can also consume objects from the bundles, which will remove
    them from the state machine state.

    For more information see:
    https://hypothesis.readthedocs.io/en/latest/stateful.html
    """

    def __init__(self) -> None:
        super().__init__()
        service = ClusterService(MagicMock())
        service.service = MockClusterService()  # mock the gRPC service
        self.cluster_client = ClusterClient(service)
        self.count_clusters = 0

    inserted_clusters: Bundle[Cluster] = Bundle("clusters")

    @rule(target=inserted_clusters, cluster=clusters())
    def create_cluster(self, cluster: Cluster) -> Cluster:
        self.count_clusters += 1
        created = self.cluster_client.create(cluster.display_name, cluster.description)
        assert created.description == cluster.description
        return created

    @rule(target=inserted_clusters, cluster=consumes(inserted_clusters), updated=clusters())
    def update_cluster(self, cluster: Cluster, updated: Cluster) -> Cluster:
        got = self.cluster_client.update(cluster.slug, name=updated.display_name, description=updated.description)
        assert got.slug == cluster.slug
        assert got.display_name == updated.display_name
        assert got.description == (updated.description if updated.description is not None else cluster.description)
        return got

    @rule(cluster=inserted_clusters)
    def get_cluster(self, cluster: Cluster) -> None:
        got = self.cluster_client.find(cluster.slug)
        assert got.display_name == cluster.display_name

    @rule(cluster=consumes(inserted_clusters))  # consumes -> remove from bundle afterwards
    def delete_cluster(self, cluster: Cluster) -> None:
        self.count_clusters -= 1
        self.cluster_client.delete(cluster.slug)

    @rule()
    def list_clusters(self) -> None:
        clusters = self.cluster_client.all()
        assert len(clusters) == self.count_clusters


# make pytest pick up the test cases from the state machine
TestClusterCRUDOperations = ClusterCRUDOperations.TestCase
