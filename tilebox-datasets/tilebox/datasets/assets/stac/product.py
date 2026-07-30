"""Immutable model inspired by the STAC product extension.

See https://github.com/stac-extensions/product.
"""

from dataclasses import dataclass

from tilebox.datasets.assets.converters import converters
from tilebox.datasets.datasets.stac.v1.product_pb2 import ProductProperties as ProductPropertiesProto


@converters.register(ProductPropertiesProto)
@dataclass(frozen=True, slots=True)
class ProductProperties:
    type: str | None = None
    timeliness: str | None = None
    timeliness_category: str | None = None
    acquisition_type: str = "unspecified"
