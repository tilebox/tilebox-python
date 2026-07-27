from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from hypothesis import given
from shapely import Geometry

from tests.data.data_access import query_filters, spatial_filter_likes, spatial_filters
from tilebox.datasets.data.data_access import QueryFilters, SpatialFilter, SpatialFilterDict
from tilebox.datasets.datasets.v1 import data_access_pb2
from tilebox.datasets.query import TimeInterval, field
from tilebox.datasets.query.id_interval import IDInterval


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


def test_query_filters_expression_to_message_and_back() -> None:
    query_filter = QueryFilters(
        temporal_extent=TimeInterval(
            datetime(2026, 7, 27, tzinfo=timezone.utc),
            datetime(2026, 7, 28, tzinfo=timezone.utc),
        ),
        filter=(field("cloud_cover") < 20) | field("cloud_cover").is_null(),
    )

    message = query_filter.to_message()
    assert len(message.expressions) == 1
    assert QueryFilters.from_message(message) == query_filter


def test_multiple_wire_expressions_are_combined_with_and() -> None:
    query_filter = QueryFilters(
        TimeInterval(
            datetime.now(tz=timezone.utc),
            datetime.now(tz=timezone.utc) + timedelta(days=1),
        )
    )
    message = query_filter.to_message()
    message.expressions.extend(
        [
            (field("cloud_cover") < 20).to_message(),
            (field("quality") >= 80).to_message(),
        ]
    )

    round_tripped = QueryFilters.from_message(message).to_message()
    assert len(round_tripped.expressions) == 1
    assert round_tripped.expressions[0].logical.operator == data_access_pb2.LOGICAL_OPERATOR_AND
    assert len(round_tripped.expressions[0].logical.operands) == 2


def test_query_filters_reject_invalid_filter() -> None:
    with pytest.raises(TypeError, match="Expected a query expression"):
        QueryFilters(
            TimeInterval(
                datetime(2026, 7, 27, tzinfo=timezone.utc),
                datetime(2026, 7, 28, tzinfo=timezone.utc),
            ),
            filter="quality > 80",  # type: ignore[arg-type]
        )


def test_query_filters_reject_invalid_interval_variants() -> None:
    with pytest.raises(ValueError, match="exactly one time or datapoint interval"):
        QueryFilters.from_message(data_access_pb2.QueryFilters())

    message = QueryFilters(
        TimeInterval(
            datetime(2026, 7, 27, tzinfo=timezone.utc),
            datetime(2026, 7, 28, tzinfo=timezone.utc),
        )
    ).to_message()
    message.datapoint_interval.CopyFrom(IDInterval(uuid4(), uuid4(), False, False).to_message())
    with pytest.raises(ValueError, match="exactly one time or datapoint interval"):
        QueryFilters.from_message(message)
