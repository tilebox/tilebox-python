"""Optional codecs for values used as Tilebox workflow task inputs.

Tasks persist their annotated fields in the task-submission wire format. The
serialization layer lets msgspec handle JSON-compatible standard-library types,
dataclasses, and containers directly, and consults this registry from msgspec's
encode/decode hooks for types that need a custom representation. Existing task
envelope rules remain unchanged: a top-level protobuf field uses its protobuf
wire bytes, while protobuf messages nested in JSON are base64 encoded.

Codecs belong here when a commonly used task-input type has a stable, portable
representation that can be reconstructed without application-specific state.
Tilebox dataset types are included for interoperability with the rest of the
SDK; broadly used geospatial value types are optional integrations. Raster
array payloads, open files, clients, and other stateful or potentially large
objects are intentionally not supported. Integration modules are imported only
when the registry first sees one of their types, so task authoring does not
eagerly import optional geospatial packages. Raster-window codecs are available
when rasterio or async-geotiff is already installed; neither is a dependency.
"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Codec:
    python_type: type
    encode: Callable[[Any], Any]
    decode: Callable[[Any], Any]
    overrides_native: bool = False


_PROVIDERS = (
    ("tilebox.datasets.", "tilebox.workflows._codecs.tilebox"),
    ("shapely.", "tilebox.workflows._codecs.shapely"),
    ("pyproj.", "tilebox.workflows._codecs.pyproj"),
    ("affine", "tilebox.workflows._codecs.affine"),
    ("odc.geo.", "tilebox.workflows._codecs.odc"),
    ("rasterio.windows", "tilebox.workflows._codecs.rasterio"),
    ("async_geotiff.", "tilebox.workflows._codecs.async_geotiff"),
)


class CodecRegistry:
    def __init__(self) -> None:
        self._codecs: dict[type, Codec] = {}
        self._cache: dict[type, Codec | None] = {}

    def register(self, codec: Codec) -> None:
        self._codecs[codec.python_type] = codec
        self._cache.clear()

    def find(self, python_type: type) -> Codec | None:
        if python_type in self._cache:
            return self._cache[python_type]

        codec = self._find_registered(python_type)
        if codec is None:
            self._load_provider(python_type)
            codec = self._find_registered(python_type)
        self._cache[python_type] = codec
        return codec

    def _find_registered(self, python_type: type) -> Codec | None:
        codec = self._codecs.get(python_type)
        if codec is not None:
            return codec

        candidates = [
            (python_type.__mro__.index(base_type), candidate)
            for base_type, candidate in self._codecs.items()
            if base_type in python_type.__mro__
        ]
        return min(candidates, default=(0, None), key=lambda item: item[0])[1]

    def _load_provider(self, python_type: type) -> None:
        modules = {base_type.__module__ for base_type in python_type.__mro__}
        for prefix, provider_module in _PROVIDERS:
            if any(module == prefix or module.startswith(prefix) for module in modules):
                provider = importlib.import_module(provider_module)
                provider.register(self, python_type)


registry = CodecRegistry()
