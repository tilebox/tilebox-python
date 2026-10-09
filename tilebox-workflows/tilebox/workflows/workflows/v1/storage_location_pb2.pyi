from google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import empty_pb2 as _empty_pb2
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

class StorageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STORAGE_TYPE_UNSPECIFIED: _ClassVar[StorageType]
    STORAGE_TYPE_GCS: _ClassVar[StorageType]
    STORAGE_TYPE_AWS_S3: _ClassVar[StorageType]
    STORAGE_TYPE_LOCAL: _ClassVar[StorageType]
    STORAGE_TYPE_AZURE_BLOB: _ClassVar[StorageType]

class StorageSubscriptionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STORAGE_SUBSCRIPTION_TYPE_UNSPECIFIED: _ClassVar[StorageSubscriptionType]
    STORAGE_SUBSCRIPTION_TYPE_AWS_SNS: _ClassVar[StorageSubscriptionType]
    STORAGE_SUBSCRIPTION_TYPE_GOOGLE_PUBSUB: _ClassVar[StorageSubscriptionType]
    STORAGE_SUBSCRIPTION_TYPE_AZURE_EVENT_GRID: _ClassVar[StorageSubscriptionType]
    STORAGE_SUBSCRIPTION_TYPE_TILEBOX_CLI: _ClassVar[StorageSubscriptionType]

class StorageEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STORAGE_EVENT_TYPE_UNSPECIFIED: _ClassVar[StorageEventType]
    STORAGE_EVENT_TYPE_CREATED: _ClassVar[StorageEventType]
STORAGE_TYPE_UNSPECIFIED: StorageType
STORAGE_TYPE_GCS: StorageType
STORAGE_TYPE_AWS_S3: StorageType
STORAGE_TYPE_LOCAL: StorageType
STORAGE_TYPE_AZURE_BLOB: StorageType
STORAGE_SUBSCRIPTION_TYPE_UNSPECIFIED: StorageSubscriptionType
STORAGE_SUBSCRIPTION_TYPE_AWS_SNS: StorageSubscriptionType
STORAGE_SUBSCRIPTION_TYPE_GOOGLE_PUBSUB: StorageSubscriptionType
STORAGE_SUBSCRIPTION_TYPE_AZURE_EVENT_GRID: StorageSubscriptionType
STORAGE_SUBSCRIPTION_TYPE_TILEBOX_CLI: StorageSubscriptionType
STORAGE_EVENT_TYPE_UNSPECIFIED: StorageEventType
STORAGE_EVENT_TYPE_CREATED: StorageEventType

class StorageLocation(_message.Message):
    __slots__ = ("id", "location", "type", "name", "reference")
    ID_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    location: str
    type: StorageType
    name: str
    reference: StorageLocationReference
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., location: _Optional[str] = ..., type: _Optional[_Union[StorageType, str]] = ..., name: _Optional[str] = ..., reference: _Optional[_Union[StorageLocationReference, _Mapping]] = ...) -> None: ...

class StorageLocationReference(_message.Message):
    __slots__ = ("aws_s3_bucket", "gcs_bucket", "azure_blob", "local", "type")
    AWS_S3_BUCKET_FIELD_NUMBER: _ClassVar[int]
    GCS_BUCKET_FIELD_NUMBER: _ClassVar[int]
    AZURE_BLOB_FIELD_NUMBER: _ClassVar[int]
    LOCAL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    aws_s3_bucket: AWSS3BucketReference
    gcs_bucket: GCSBucketReference
    azure_blob: AzureBlobReference
    local: LocalReference
    type: StorageType
    def __init__(self, aws_s3_bucket: _Optional[_Union[AWSS3BucketReference, _Mapping]] = ..., gcs_bucket: _Optional[_Union[GCSBucketReference, _Mapping]] = ..., azure_blob: _Optional[_Union[AzureBlobReference, _Mapping]] = ..., local: _Optional[_Union[LocalReference, _Mapping]] = ..., type: _Optional[_Union[StorageType, str]] = ...) -> None: ...

class AWSS3BucketReference(_message.Message):
    __slots__ = ("bucket", "region")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    region: str
    def __init__(self, bucket: _Optional[str] = ..., region: _Optional[str] = ...) -> None: ...

class GCSBucketReference(_message.Message):
    __slots__ = ("bucket", "project_id", "location")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    project_id: str
    location: str
    def __init__(self, bucket: _Optional[str] = ..., project_id: _Optional[str] = ..., location: _Optional[str] = ...) -> None: ...

class AzureBlobReference(_message.Message):
    __slots__ = ("storage_account_resource_id", "container", "region")
    STORAGE_ACCOUNT_RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    storage_account_resource_id: str
    container: str
    region: str
    def __init__(self, storage_account_resource_id: _Optional[str] = ..., container: _Optional[str] = ..., region: _Optional[str] = ...) -> None: ...

class LocalReference(_message.Message):
    __slots__ = ("path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    path: str
    def __init__(self, path: _Optional[str] = ...) -> None: ...

class TriggeredJob(_message.Message):
    __slots__ = ("job_id", "automation_id", "glob_pattern")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    AUTOMATION_ID_FIELD_NUMBER: _ClassVar[int]
    GLOB_PATTERN_FIELD_NUMBER: _ClassVar[int]
    job_id: _id_pb2.ID
    automation_id: _id_pb2.ID
    glob_pattern: str
    def __init__(self, job_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., automation_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., glob_pattern: _Optional[str] = ...) -> None: ...

class TriggeredJobs(_message.Message):
    __slots__ = ("triggered_jobs",)
    TRIGGERED_JOBS_FIELD_NUMBER: _ClassVar[int]
    triggered_jobs: _containers.RepeatedCompositeFieldContainer[TriggeredJob]
    def __init__(self, triggered_jobs: _Optional[_Iterable[_Union[TriggeredJob, _Mapping]]] = ...) -> None: ...

class CreateStorageLocationRequest(_message.Message):
    __slots__ = ("name", "reference")
    NAME_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_FIELD_NUMBER: _ClassVar[int]
    name: str
    reference: StorageLocationReference
    def __init__(self, name: _Optional[str] = ..., reference: _Optional[_Union[StorageLocationReference, _Mapping]] = ...) -> None: ...

class UpdateStorageLocationRequest(_message.Message):
    __slots__ = ("storage_location_id", "name")
    STORAGE_LOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    storage_location_id: _id_pb2.ID
    name: str
    def __init__(self, storage_location_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class AWSSNSStorageSubscription(_message.Message):
    __slots__ = ("topic_arn", "message_format")
    TOPIC_ARN_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FORMAT_FIELD_NUMBER: _ClassVar[int]
    topic_arn: str
    message_format: str
    def __init__(self, topic_arn: _Optional[str] = ..., message_format: _Optional[str] = ...) -> None: ...

class GooglePubSubStorageSubscription(_message.Message):
    __slots__ = ("subscription", "service_account_email", "audience")
    SUBSCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_EMAIL_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    subscription: str
    service_account_email: str
    audience: str
    def __init__(self, subscription: _Optional[str] = ..., service_account_email: _Optional[str] = ..., audience: _Optional[str] = ...) -> None: ...

class AzureEventGridStorageSubscription(_message.Message):
    __slots__ = ("webhook_secret_header", "webhook_secret", "webhook_secret_hash")
    WEBHOOK_SECRET_HEADER_FIELD_NUMBER: _ClassVar[int]
    WEBHOOK_SECRET_FIELD_NUMBER: _ClassVar[int]
    WEBHOOK_SECRET_HASH_FIELD_NUMBER: _ClassVar[int]
    webhook_secret_header: str
    webhook_secret: str
    webhook_secret_hash: bytes
    def __init__(self, webhook_secret_header: _Optional[str] = ..., webhook_secret: _Optional[str] = ..., webhook_secret_hash: _Optional[bytes] = ...) -> None: ...

class StorageSubscription(_message.Message):
    __slots__ = ("id", "storage_location_id", "type", "endpoint", "created_at", "aws_sns", "google_pubsub", "azure_event_grid")
    ID_FIELD_NUMBER: _ClassVar[int]
    STORAGE_LOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    AWS_SNS_FIELD_NUMBER: _ClassVar[int]
    GOOGLE_PUBSUB_FIELD_NUMBER: _ClassVar[int]
    AZURE_EVENT_GRID_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    storage_location_id: _id_pb2.ID
    type: StorageSubscriptionType
    endpoint: str
    created_at: _timestamp_pb2.Timestamp
    aws_sns: AWSSNSStorageSubscription
    google_pubsub: GooglePubSubStorageSubscription
    azure_event_grid: AzureEventGridStorageSubscription
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., storage_location_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., type: _Optional[_Union[StorageSubscriptionType, str]] = ..., endpoint: _Optional[str] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., aws_sns: _Optional[_Union[AWSSNSStorageSubscription, _Mapping]] = ..., google_pubsub: _Optional[_Union[GooglePubSubStorageSubscription, _Mapping]] = ..., azure_event_grid: _Optional[_Union[AzureEventGridStorageSubscription, _Mapping]] = ...) -> None: ...

class CreateStorageSubscriptionRequest(_message.Message):
    __slots__ = ("storage_location_id", "type", "aws_sns", "google_pubsub", "azure_event_grid")
    STORAGE_LOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    AWS_SNS_FIELD_NUMBER: _ClassVar[int]
    GOOGLE_PUBSUB_FIELD_NUMBER: _ClassVar[int]
    AZURE_EVENT_GRID_FIELD_NUMBER: _ClassVar[int]
    storage_location_id: _id_pb2.ID
    type: StorageSubscriptionType
    aws_sns: AWSSNSStorageSubscription
    google_pubsub: GooglePubSubStorageSubscription
    azure_event_grid: AzureEventGridStorageSubscription
    def __init__(self, storage_location_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., type: _Optional[_Union[StorageSubscriptionType, str]] = ..., aws_sns: _Optional[_Union[AWSSNSStorageSubscription, _Mapping]] = ..., google_pubsub: _Optional[_Union[GooglePubSubStorageSubscription, _Mapping]] = ..., azure_event_grid: _Optional[_Union[AzureEventGridStorageSubscription, _Mapping]] = ...) -> None: ...

class ListStorageSubscriptionsRequest(_message.Message):
    __slots__ = ("storage_location_id",)
    STORAGE_LOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    storage_location_id: _id_pb2.ID
    def __init__(self, storage_location_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class StorageSubscriptions(_message.Message):
    __slots__ = ("subscriptions",)
    SUBSCRIPTIONS_FIELD_NUMBER: _ClassVar[int]
    subscriptions: _containers.RepeatedCompositeFieldContainer[StorageSubscription]
    def __init__(self, subscriptions: _Optional[_Iterable[_Union[StorageSubscription, _Mapping]]] = ...) -> None: ...

class StorageSubscriptionEvent(_message.Message):
    __slots__ = ("id", "object_key", "type", "event_time", "received_at", "triggered_jobs", "storage_subscription_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    EVENT_TIME_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_AT_FIELD_NUMBER: _ClassVar[int]
    TRIGGERED_JOBS_FIELD_NUMBER: _ClassVar[int]
    STORAGE_SUBSCRIPTION_ID_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    object_key: str
    type: StorageEventType
    event_time: _timestamp_pb2.Timestamp
    received_at: _timestamp_pb2.Timestamp
    triggered_jobs: _containers.RepeatedCompositeFieldContainer[TriggeredJob]
    storage_subscription_id: _id_pb2.ID
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., object_key: _Optional[str] = ..., type: _Optional[_Union[StorageEventType, str]] = ..., event_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., received_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., triggered_jobs: _Optional[_Iterable[_Union[TriggeredJob, _Mapping]]] = ..., storage_subscription_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class ListStorageSubscriptionEventsRequest(_message.Message):
    __slots__ = ("storage_location_id", "page")
    STORAGE_LOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    storage_location_id: _id_pb2.ID
    page: _query_pb2.Pagination
    def __init__(self, storage_location_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...

class StorageSubscriptionEvents(_message.Message):
    __slots__ = ("events", "next_page")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[StorageSubscriptionEvent]
    next_page: _query_pb2.Pagination
    def __init__(self, events: _Optional[_Iterable[_Union[StorageSubscriptionEvent, _Mapping]]] = ..., next_page: _Optional[_Union[_query_pb2.Pagination, _Mapping]] = ...) -> None: ...

class StorageLocations(_message.Message):
    __slots__ = ("locations",)
    LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    locations: _containers.RepeatedCompositeFieldContainer[StorageLocation]
    def __init__(self, locations: _Optional[_Iterable[_Union[StorageLocation, _Mapping]]] = ...) -> None: ...

class TriggeredStorageEvent(_message.Message):
    __slots__ = ("storage_location_id", "type", "location")
    STORAGE_LOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    storage_location_id: _id_pb2.ID
    type: StorageEventType
    location: str
    def __init__(self, storage_location_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., type: _Optional[_Union[StorageEventType, str]] = ..., location: _Optional[str] = ...) -> None: ...
