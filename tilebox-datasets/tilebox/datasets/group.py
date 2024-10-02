from textwrap import indent, wrap
from typing import Any


class Group:
    """
    A group of tilebox clients that can be accessed by attribute access or as a mapping.

    Each client in this group is a RemoteTimeseriesDataset or another TileboxDatasets. This way client groups
    can be nested recursively.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}

    def _add(self, name: str, client: Any) -> None:
        if not isinstance(client, Group) and not hasattr(client, "_dataset"):
            raise ValueError(f"Expected a TileboxDataset or Group, got {type(client)}")
        setattr(self, name, client)  # add the client as an attribute, so auto-complete works for it
        self._clients[name] = client

    def __repr__(self) -> str:
        text = ""

        for name, client in self._clients.items():
            if isinstance(client, Group):
                subrepr = repr(client)
                text += f"{name}:\n"
                text += indent(subrepr, "    ")
            else:
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
