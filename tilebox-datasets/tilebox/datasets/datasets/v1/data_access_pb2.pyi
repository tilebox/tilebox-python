from tilebox.datasets.datasets.v1 import core_pb2 as _core_pb2
from tilebox.datasets.datasets.v1 import well_known_types_pb2 as _well_known_types_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

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
SPATIAL_FILTER_MODE_UNSPECIFIED: SpatialFilterMode
SPATIAL_FILTER_MODE_INTERSECTS: SpatialFilterMode
SPATIAL_FILTER_MODE_CONTAINS: SpatialFilterMode
SPATIAL_COORDINATE_SYSTEM_UNSPECIFIED: SpatialCoordinateSystem
SPATIAL_COORDINATE_SYSTEM_CARTESIAN: SpatialCoordinateSystem
SPATIAL_COORDINATE_SYSTEM_SPHERICAL: SpatialCoordinateSystem

class GetDatasetForIntervalRequest(_message.Message):
    __slots__ = ("collection_id", "time_interval", "datapoint_interval", "page", "skip_data", "skip_meta")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    SKIP_META_FIELD_NUMBER: _ClassVar[int]
    collection_id: str
    time_interval: _query_pb2.TimeInterval
    datapoint_interval: _query_pb2.IDInterval
    page: _core_pb2.LegacyPagination
    skip_data: bool
    skip_meta: bool
    def __init__(self, collection_id: _Optional[str] = ..., time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[_query_pb2.IDInterval, _Mapping]] = ..., page: _Optional[_Union[_core_pb2.LegacyPagination, _Mapping]] = ..., skip_data: bool = ..., skip_meta: bool = ...) -> None: ...

class GetDatapointByIdRequest(_message.Message):
    __slots__ = ("collection_id", "id", "skip_data")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_id: str
    id: str
    skip_data: bool
    def __init__(self, collection_id: _Optional[str] = ..., id: _Optional[str] = ..., skip_data: bool = ...) -> None: ...

class QueryByIDRequest(_message.Message):
    __slots__ = ("collection_ids", "id", "skip_data")
    COLLECTION_IDS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_ids: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    id: _id_pb2.ID
    skip_data: bool
    def __init__(self, collection_ids: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ..., id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., skip_data: bool = ...) -> None: ...

class QueryFilters(_message.Message):
    __slots__ = ("time_interval", "datapoint_interval", "spatial_extent")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    SPATIAL_EXTENT_FIELD_NUMBER: _ClassVar[int]
    time_interval: _query_pb2.TimeInterval
    datapoint_interval: _query_pb2.IDInterval
    spatial_extent: SpatialFilter
    def __init__(self, time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., datapoint_interval: _Optional[_Union[_query_pb2.IDInterval, _Mapping]] = ..., spatial_extent: _Optional[_Union[SpatialFilter, _Mapping]] = ...) -> None: ...

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
    __slots__ = ("collection_ids", "filters", "page", "skip_data")
    COLLECTION_IDS_FIELD_NUMBER: _ClassVar[int]
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SKIP_DATA_FIELD_NUMBER: _ClassVar[int]
    collection_ids: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    filters: QueryFilters
    page: _query_pb2.Pagination
    skip_data: bool
    def __init__(self, collection_ids: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ..., filters: _Optional[_Union[QueryFilters, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ..., skip_data: bool = ...) -> None: ...

class QueryResultPage(_message.Message):
    __slots__ = ("data", "next_page")
    DATA_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    data: _core_pb2.RepeatedAny
    next_page: _query_pb2.Pagination
    def __init__(self, data: _Optional[_Union[_core_pb2.RepeatedAny, _Mapping]] = ..., next_page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...
