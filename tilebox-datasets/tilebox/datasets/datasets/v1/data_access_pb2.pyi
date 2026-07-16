from tilebox.datasets.datasets.v1 import core_pb2 as _core_pb2
from tilebox.datasets.datasets.v1 import well_known_types_pb2 as _well_known_types_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LogicalOperator(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LOGICAL_OPERATOR_UNSPECIFIED: _ClassVar[LogicalOperator]
    LOGICAL_OPERATOR_AND: _ClassVar[LogicalOperator]
    LOGICAL_OPERATOR_OR: _ClassVar[LogicalOperator]
    LOGICAL_OPERATOR_NOT: _ClassVar[LogicalOperator]

class FieldComparisonOperator(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FIELD_COMPARISON_OPERATOR_UNSPECIFIED: _ClassVar[FieldComparisonOperator]
    FIELD_COMPARISON_OPERATOR_EQUAL: _ClassVar[FieldComparisonOperator]
    FIELD_COMPARISON_OPERATOR_NOT_EQUAL: _ClassVar[FieldComparisonOperator]
    FIELD_COMPARISON_OPERATOR_LESS_THAN: _ClassVar[FieldComparisonOperator]
    FIELD_COMPARISON_OPERATOR_LESS_THAN_OR_EQUAL: _ClassVar[FieldComparisonOperator]
    FIELD_COMPARISON_OPERATOR_GREATER_THAN: _ClassVar[FieldComparisonOperator]
    FIELD_COMPARISON_OPERATOR_GREATER_THAN_OR_EQUAL: _ClassVar[FieldComparisonOperator]

class SpatialFilterMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SPATIAL_FILTER_MODE_UNSPECIFIED: _ClassVar[SpatialFilterMode]
    SPATIAL_FILTER_MODE_INTERSECTS: _ClassVar[SpatialFilterMode]
    SPATIAL_FILTER_MODE_CONTAINS: _ClassVar[SpatialFilterMode]

class SpatialCoordinateSystem(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SPATIAL_COORDINATE_SYSTEM_UNSPECIFIED: _ClassVar[SpatialCoordinateSystem]
    SPATIAL_COORDINATE_SYSTEM_CARTESIAN: _ClassVar[SpatialCoordinateSystem]
    SPATIAL_COORDINATE_SYSTEM_SPHERICAL: _ClassVar[SpatialCoordinateSystem]
LOGICAL_OPERATOR_UNSPECIFIED: LogicalOperator
LOGICAL_OPERATOR_AND: LogicalOperator
LOGICAL_OPERATOR_OR: LogicalOperator
LOGICAL_OPERATOR_NOT: LogicalOperator
FIELD_COMPARISON_OPERATOR_UNSPECIFIED: FieldComparisonOperator
FIELD_COMPARISON_OPERATOR_EQUAL: FieldComparisonOperator
FIELD_COMPARISON_OPERATOR_NOT_EQUAL: FieldComparisonOperator
FIELD_COMPARISON_OPERATOR_LESS_THAN: FieldComparisonOperator
FIELD_COMPARISON_OPERATOR_LESS_THAN_OR_EQUAL: FieldComparisonOperator
FIELD_COMPARISON_OPERATOR_GREATER_THAN: FieldComparisonOperator
FIELD_COMPARISON_OPERATOR_GREATER_THAN_OR_EQUAL: FieldComparisonOperator
SPATIAL_FILTER_MODE_UNSPECIFIED: SpatialFilterMode
SPATIAL_FILTER_MODE_INTERSECTS: SpatialFilterMode
SPATIAL_FILTER_MODE_CONTAINS: SpatialFilterMode
SPATIAL_COORDINATE_SYSTEM_UNSPECIFIED: SpatialCoordinateSystem
SPATIAL_COORDINATE_SYSTEM_CARTESIAN: SpatialCoordinateSystem
SPATIAL_COORDINATE_SYSTEM_SPHERICAL: SpatialCoordinateSystem

class QueryByIDRequest(_message.Message):
    __slots__ = ("dataset_id", "collection_ids", "id", "skip_data")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_IDS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    dataset_id: _id_pb2.ID
    collection_ids: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    id: _id_pb2.ID
    skip_data: bool
    def __init__(self, dataset_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., collection_ids: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ..., id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., skip_data: bool = ...) -> None: ...

class QueryFilters(_message.Message):
    __slots__ = ("time_interval", "datapoint_interval", "spatial_extent", "expressions")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    SPATIAL_EXTENT_FIELD_NUMBER: _ClassVar[int]
    EXPRESSIONS_FIELD_NUMBER: _ClassVar[int]
    time_interval: _query_pb2.TimeInterval
    datapoint_interval: _query_pb2.IDInterval
    spatial_extent: SpatialFilter
    expressions: _containers.RepeatedCompositeFieldContainer[FilterExpression]
    def __init__(self, time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[_query_pb2.IDInterval, _Mapping]] = ..., spatial_extent: _Optional[_Union[SpatialFilter, _Mapping]] = ..., expressions: _Optional[_Iterable[_Union[FilterExpression, _Mapping]]] = ...) -> None: ...

class FilterExpression(_message.Message):
    __slots__ = ("logical", "comparison", "is_null")
    LOGICAL_FIELD_NUMBER: _ClassVar[int]
    COMPARISON_FIELD_NUMBER: _ClassVar[int]
    IS_NULL_FIELD_NUMBER: _ClassVar[int]
    logical: LogicalExpression
    comparison: FieldComparison
    is_null: FieldNullCheck
    def __init__(self, logical: _Optional[_Union[LogicalExpression, _Mapping]] = ..., comparison: _Optional[_Union[FieldComparison, _Mapping]] = ..., is_null: _Optional[_Union[FieldNullCheck, _Mapping]] = ...) -> None: ...

class LogicalExpression(_message.Message):
    __slots__ = ("operator", "operands")
    OPERATOR_FIELD_NUMBER: _ClassVar[int]
    OPERANDS_FIELD_NUMBER: _ClassVar[int]
    operator: LogicalOperator
    operands: _containers.RepeatedCompositeFieldContainer[FilterExpression]
    def __init__(self, operator: _Optional[_Union[LogicalOperator, str]] = ..., operands: _Optional[_Iterable[_Union[FilterExpression, _Mapping]]] = ...) -> None: ...

class FieldComparison(_message.Message):
    __slots__ = ("field_name", "operator", "value")
    FIELD_NAME_FIELD_NUMBER: _ClassVar[int]
    OPERATOR_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    field_name: str
    operator: FieldComparisonOperator
    value: FieldQueryValue
    def __init__(self, field_name: _Optional[str] = ..., operator: _Optional[_Union[FieldComparisonOperator, str]] = ..., value: _Optional[_Union[FieldQueryValue, _Mapping]] = ...) -> None: ...

class FieldNullCheck(_message.Message):
    __slots__ = ("field_name",)
    FIELD_NAME_FIELD_NUMBER: _ClassVar[int]
    field_name: str
    def __init__(self, field_name: _Optional[str] = ...) -> None: ...

class FieldQueryValue(_message.Message):
    __slots__ = ("bool_value", "int64_value", "uint64_value", "double_value", "string_value", "timestamp_value", "duration_value", "enum_name", "bytes_value")
    BOOL_VALUE_FIELD_NUMBER: _ClassVar[int]
    INT64_VALUE_FIELD_NUMBER: _ClassVar[int]
    UINT64_VALUE_FIELD_NUMBER: _ClassVar[int]
    DOUBLE_VALUE_FIELD_NUMBER: _ClassVar[int]
    STRING_VALUE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_VALUE_FIELD_NUMBER: _ClassVar[int]
    DURATION_VALUE_FIELD_NUMBER: _ClassVar[int]
    ENUM_NAME_FIELD_NUMBER: _ClassVar[int]
    BYTES_VALUE_FIELD_NUMBER: _ClassVar[int]
    bool_value: bool
    int64_value: int
    uint64_value: int
    double_value: float
    string_value: str
    timestamp_value: _timestamp_pb2.Timestamp
    duration_value: _duration_pb2.Duration
    enum_name: str
    bytes_value: bytes
    def __init__(self, bool_value: bool = ..., int64_value: _Optional[int] = ..., uint64_value: _Optional[int] = ..., double_value: _Optional[float] = ..., string_value: _Optional[str] = ..., timestamp_value: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., duration_value: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., enum_name: _Optional[str] = ..., bytes_value: _Optional[bytes] = ...) -> None: ...

class SpatialFilter(_message.Message):
    __slots__ = ("geometry", "mode", "coordinate_system")
    GEOMETRY_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    COORDINATE_SYSTEM_FIELD_NUMBER: _ClassVar[int]
    geometry: _well_known_types_pb2.Geometry
    mode: SpatialFilterMode
    coordinate_system: SpatialCoordinateSystem
    def __init__(self, geometry: _Optional[_Union[_well_known_types_pb2.Geometry, _Mapping]] = ..., mode: _Optional[_Union[SpatialFilterMode, str]] = ..., coordinate_system: _Optional[_Union[SpatialCoordinateSystem, str]] = ...) -> None: ...

class QueryRequest(_message.Message):
    __slots__ = ("dataset_id", "collection_ids", "filters", "page", "skip_data")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_IDS_FIELD_NUMBER: _ClassVar[int]
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    dataset_id: _id_pb2.ID
    collection_ids: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    filters: QueryFilters
    page: _query_pb2.Pagination
    skip_data: bool
    def __init__(self, dataset_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., collection_ids: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ..., filters: _Optional[_Union[QueryFilters, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ..., skip_data: bool = ...) -> None: ...

class QueryResultPage(_message.Message):
    __slots__ = ("data", "next_page")
    DATA_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    data: _core_pb2.RepeatedAny
    next_page: _query_pb2.Pagination
    def __init__(self, data: _Optional[_Union[_core_pb2.RepeatedAny, _Mapping]] = ..., next_page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...
