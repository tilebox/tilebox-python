from hypothesis import given
from shapely import Geometry

from tests.data.data_access import query_filters, spatial_filter_likes, spatial_filters
from tilebox.datasets.data.data_access import QueryFilters, SpatialFilter, SpatialFilterDict


@given(spatial_filters())
def test_spatial_filter_to_message_and_back(s: SpatialFilter) -> None:
    assert SpatialFilter.from_message(s.to_message()) == s


@given(spatial_filter_likes())
def test_parse_spatial_filter_like(spatial_filter_like: Geometry | SpatialFilterDict) -> None:
    spatial_filter = SpatialFilter.parse(spatial_filter_like)
    if isinstance(spatial_filter_like, Geometry):
        assert spatial_filter.geometry == spatial_filter_like
        assert spatial_filter.mode is None
        assert spatial_filter.coordinate_system is None
    else:
        assert spatial_filter.geometry == spatial_filter_like["geometry"]
        if "mode" not in spatial_filter_like:
            assert spatial_filter.mode is None
        else:
            assert spatial_filter.mode is not None

        if "coordinate_system" not in spatial_filter_like:
            assert spatial_filter.coordinate_system is None
        else:
            assert spatial_filter.coordinate_system is not None


@given(query_filters())
def test_query_filters_to_message_and_back(q: QueryFilters) -> None:
    assert QueryFilters.from_message(q.to_message()) == q
