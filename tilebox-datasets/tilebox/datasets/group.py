from textwrap import indent, wrap
from typing import Any

from _tilebox.grpc.aio.syncify import Syncifiable
from tilebox.datasets.data.datasets import Dataset, DatasetGroup
from tilebox.datasets.service import TileboxDatasetService
from tilebox.datasets.timeseries import RemoteTimeseriesDataset


class TileboxDatasetGroup(Syncifiable):
    """
    A group of tilebox clients that can be accessed by attribute access or as a mapping.

    Each client in this group is a RemoteTimeseriesDataset or another TileboxDatasets. This way client groups
    can be nested recursively.
    """

    def __init__(self) -> None:
        self._clients: dict[str, RemoteTimeseriesDataset | TileboxDatasetGroup] = {}

    def _syncify(self) -> None:
        """
        Convert this client group to a synchronous client group. This will wrap all async methods in a asyncio.run()
        call and return the result, therefore appearing to the outside as a completely synchronous client.
        """
        super()._syncify()

        for subclient in self._clients.values():
            if isinstance(subclient, Syncifiable):  # this will also recursively apply to nested client groups
                subclient._syncify()  # noqa: SLF001

    def _add(self, name: str, client: "RemoteTimeseriesDataset | TileboxDatasetGroup") -> None:
        setattr(self, name, client)  # add the client as an attribute, so auto-complete works for it
        self._clients[name] = client

    def __repr__(self) -> str:
        text = ""

        for name, client in self._clients.items():
            if isinstance(client, TileboxDatasetGroup):
                subrepr = repr(client)
                text += f"{name}:\n"
                text += indent(subrepr, "    ")
            elif isinstance(client, RemoteTimeseriesDataset):
                dataset = client._dataset  # noqa: SLF001
                description = "\n".join(wrap(dataset.summary or "", 80, initial_indent="", subsequent_indent="    "))
                text += f"{name}: {description}\n"
        return text

    def __getattr__(self, name: str) -> Any:
        """
        __getattr__ is only a fallback for when an attribute is not set, which shouldn't be the case,
        because all clients are registered as attributes in _register_client.

        So this method will actually only be called when trying to access an attribute that doesn't exist.

        But it is implemented anyway, to make the type checker understand what is going on.
        """
        if name in self._clients:
            return self._clients[name]
        raise AttributeError(f"No such dataset or dataset group '{name}'")


def construct_root_group(
    datasets: list[Dataset], groups: list[DatasetGroup], service: TileboxDatasetService
) -> TileboxDatasetGroup:
    root = TileboxDatasetGroup()
    group_lookup = {g.id: TileboxDatasetGroup() for g in groups}

    # recursively nest groups based on their parent_id
    for g in groups:
        parent = group_lookup[g.parent_id] if g.parent_id is not None else root
        parent._add(g.code_name, group_lookup[g.id])  # noqa: SLF001

    # add datasets to their respective groups
    for d in datasets:
        group = group_lookup[d.group_id]
        group._add(d.code_name, RemoteTimeseriesDataset(service, d))  # noqa: SLF001

    return root
