from pyproj import CRS

from tilebox.workflows._codec import Codec, CodecRegistry


def _encode_crs(crs: CRS) -> str:
    authority = crs.to_authority()
    return f"{authority[0]}:{authority[1]}" if authority is not None else crs.to_wkt()


def register(registry: CodecRegistry, _: type) -> None:
    registry.register(Codec(CRS, _encode_crs, CRS.from_user_input))
