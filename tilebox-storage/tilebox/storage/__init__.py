from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tilebox.storage._sync import (
        ASFStorageClient,
        CopernicusStorageClient,
        LocalFileSystemStorageClient,
        UmbraStorageClient,
        USGSLandsatStorageClient,
    )

__all__ = [
    "ASFStorageClient",
    "CopernicusStorageClient",
    "LocalFileSystemStorageClient",
    "USGSLandsatStorageClient",
    "UmbraStorageClient",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    storage_client = getattr(import_module("tilebox.storage._sync"), name)
    # Cache the resolved export so subsequent access uses normal module lookup instead of calling __getattr__ again.
    globals()[name] = storage_client
    return storage_client


def __dir__() -> list[str]:
    # Include public lazy exports in dir(module) before they have been loaded.
    return sorted(set(globals()) | set(__all__))
