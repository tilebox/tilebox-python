from affine import Affine

from tilebox.workflows._codec import Codec, CodecRegistry


def register(registry: CodecRegistry, _: type) -> None:
    registry.register(
        Codec(Affine, lambda affine: list(affine[:6]), lambda value: Affine(*value), overrides_native=True)
    )
