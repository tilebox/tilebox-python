from opentelemetry.proto.logs.v1 import logs_pb2 as _logs_pb2
from opentelemetry.proto.trace.v1 import trace_pb2 as _trace_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class QueryJobLogsRequest(_message.Message):
    __slots__ = ("job_id", "page", "sort_direction")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SORT_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    page: _query_pb2.Pagination
    sort_direction: _query_pb2.SortDirection
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ..., sort_direction: _Optional[_Union[_query_pb2.SortDirection, str]] = ...) -> None: ...

class QueryLogsInIntervalRequest(_message.Message):
    __slots__ = ("time_interval", "page", "sort_direction")
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SORT_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    time_interval: _query_pb2.TimeInterval
    page: _query_pb2.Pagination
    sort_direction: _query_pb2.SortDirection
    def __init__(self, time_interval: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ..., sort_direction: _Optional[_Union[_query_pb2.SortDirection, str]] = ...) -> None: ...

class PaginatedLogsData(_message.Message):
    __slots__ = ("resource_logs", "next_page")
    RESOURCE_LOGS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    resource_logs: _containers.RepeatedCompositeFieldContainer[_logs_pb2.ResourceLogs]
    next_page: _query_pb2.Pagination
    def __init__(self, resource_logs: _Optional[_Iterable[_Union[_logs_pb2.ResourceLogs, _Mapping]]] = ..., next_page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...

class QueryJobSpansRequest(_message.Message):
    __slots__ = ("job_id", "page", "sort_direction")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SORT_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    page: _query_pb2.Pagination
    sort_direction: _query_pb2.SortDirection
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ..., sort_direction: _Optional[_Union[_query_pb2.SortDirection, str]] = ...) -> None: ...

class PaginatedSpansData(_message.Message):
    __slots__ = ("resource_spans", "next_page")
    RESOURCE_SPANS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    resource_spans: _containers.RepeatedCompositeFieldContainer[_trace_pb2.ResourceSpans]
    next_page: _query_pb2.Pagination
    def __init__(self, resource_spans: _Optional[_Iterable[_Union[_trace_pb2.ResourceSpans, _Mapping]]] = ..., next_page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...
