from types import SimpleNamespace
from typing import cast

import pytest

async_geotiff = pytest.importorskip("async_geotiff")
from affine import Affine  # noqa: E402

Window = async_geotiff.Window
GeoTIFF = async_geotiff.GeoTIFF

from tilebox.storage.geotiff import window_from_bounds  # noqa: E402


def _geotiff() -> GeoTIFF:
    return cast(
        GeoTIFF,
        SimpleNamespace(
            crs="EPSG:4326",
            transform=Affine(1, 0, 0, 0, -1, 10),
            width=10,
            height=10,
        ),
    )


def test_window_from_projected_bounds_rounds_outward() -> None:
    window = window_from_bounds(_geotiff(), (1.2, 2.2, 4.1, 7.8), crs="EPSG:4326")
    assert window == Window(col_off=1, row_off=2, width=4, height=6)


def test_window_clips_partial_overlap() -> None:
    assert window_from_bounds(_geotiff(), (-3, 8, 3, 12), crs="EPSG:4326") == Window(0, 0, 3, 2)


def test_window_requires_full_containment() -> None:
    with pytest.raises(ValueError, match="not fully contained"):
        window_from_bounds(_geotiff(), (-1, 2, 3, 5), crs="EPSG:4326", require_fully_contained=True)


def test_window_rejects_empty_malformed_and_antimeridian_bounds() -> None:
    with pytest.raises(ValueError, match="do not intersect"):
        window_from_bounds(_geotiff(), (20, 20, 21, 21), crs="EPSG:4326")
    with pytest.raises(ValueError, match="bottom"):
        window_from_bounds(_geotiff(), (1, 4, 2, 3), crs="EPSG:3857")
    with pytest.raises(ValueError, match=r"split.*antimeridian"):
        window_from_bounds(_geotiff(), (170, -10, -170, 10), crs="EPSG:4326")
