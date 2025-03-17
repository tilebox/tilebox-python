from pathlib import Path

import pytest
from shapely import MultiPolygon

from tilebox.datasets.datasetsv1.well_known_types_pb2 import GeobufData
from tilebox.datasets.protobuf_conversion.geobuf import parse_geobuf


def _read_geobuf(name: str) -> GeobufData:
    file = Path(__file__).parent.parent / "testdata" / "geobuf" / name

    with file.open("rb") as f:
        data = f.read()

    obj = GeobufData()
    obj.ParseFromString(data)
    return obj


def test_decode_polygon_geobuf() -> None:
    poly_geobuf = _read_geobuf("polygon.binpb")

    poly = parse_geobuf(poly_geobuf)
    assert poly.bounds == (pytest.approx(-180.0), pytest.approx(65.808014), pytest.approx(180.0), pytest.approx(90.0))


def test_decode_multipolygon_geobuf() -> None:
    multipoly_geobuf = _read_geobuf("multipolygon.binpb")

    poly = parse_geobuf(multipoly_geobuf)
    assert isinstance(poly, MultiPolygon)
    sub_polys = list(poly.geoms)
    assert len(sub_polys) == 2, "Expected 2 sub-polygons"
    assert sub_polys[0].bounds == (
        pytest.approx(-180.0),
        pytest.approx(57.88233),
        pytest.approx(-123.409134),
        pytest.approx(83.292342425),
    )
    assert sub_polys[1].bounds == (
        pytest.approx(126.83469),
        pytest.approx(62.794425427),
        pytest.approx(180.0),
        pytest.approx(84.15669),
    )


def test_decode_multipolygon_with_holes_geobuf() -> None:
    multipoly_geobuf = _read_geobuf("multipolygon_with_holes.binpb")

    poly = parse_geobuf(multipoly_geobuf)
    assert isinstance(poly, MultiPolygon)
    sub_polys = list(poly.geoms)
    assert len(sub_polys) == 2, "Expected 2 sub-polygons"

    assert sub_polys[0].bounds == (
        pytest.approx(-180.0),
        pytest.approx(-89.999987328),
        pytest.approx(180),
        pytest.approx(89.552340092),
    )
    assert len(sub_polys[0].interiors) == 1, "Expected one hole in subpolygon 0"
    assert sub_polys[0].interiors[0].bounds == (
        pytest.approx(0),
        pytest.approx(80.1859136),
        pytest.approx(55.376515584),
        pytest.approx(85.43048645),
    )

    assert sub_polys[1].bounds == (
        pytest.approx(0),
        pytest.approx(-89.690675287),
        pytest.approx(1.547255492),
        pytest.approx(-85.05115885),
    )
