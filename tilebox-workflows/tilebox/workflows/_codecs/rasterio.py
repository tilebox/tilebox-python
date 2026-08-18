from importlib import import_module
from typing import Any

from tilebox.workflows._codec import Codec, CodecRegistry

Window: Any = import_module("rasterio.windows").Window


def _encode_window(window: Any) -> dict[str, Any]:
    return {
        "row_offset": window.row_off,
        "column_offset": window.col_off,
        "height": window.height,
        "width": window.width,
    }


def _decode_window(value: dict[str, Any]) -> Any:
    return Window(
        value["column_offset"],
        value["row_offset"],
        value["width"],
        value["height"],
    )


def register(registry: CodecRegistry, _: type) -> None:
    registry.register(Codec(Window, _encode_window, _decode_window, overrides_native=True))
