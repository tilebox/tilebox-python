from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TypedDict, get_args, get_origin
from uuid import UUID

import numpy as np
from google.protobuf import duration_pb2, timestamp_pb2
from google.protobuf.descriptor_pb2 import FieldDescriptorProto, FileDescriptorSet
from shapely import Geometry
from typing_extensions import NotRequired, Required

from tilebox.datasets.datasets.v1 import core_pb2, dataset_type_pb2, datasets_pb2, well_known_types_pb2
from tilebox.datasets.uuid import uuid_message_to_optional_uuid, uuid_message_to_uuid, uuid_to_uuid_message


class DatasetKind(Enum):
    TEMPORAL = dataset_type_pb2.DATASET_KIND_TEMPORAL
    """A dataset that contains a timestamp field."""
    SPATIOTEMPORAL = dataset_type_pb2.DATASET_KIND_SPATIOTEMPORAL
    """A dataset that contains a timestamp field and a geometry field."""


_dataset_kind_int_to_enum = {kind.value: kind for kind in DatasetKind}


@dataclass(frozen=True)
class FieldAnnotation:
    description: str
    example_value: str

    @classmethod
    def from_message(cls, annotation: dataset_type_pb2.FieldAnnotation) -> "FieldAnnotation":
        return cls(description=annotation.description, example_value=annotation.example_value)

    def to_message(self) -> dataset_type_pb2.FieldAnnotation:
        return dataset_type_pb2.FieldAnnotation(description=self.description, example_value=self.example_value)


class FieldDict(TypedDict):
    name: Required[str]
    type: Required[
        type[str]
        | type[list[str]]
        | type[bytes]
        | type[list[bytes]]
        | type[bool]
        | type[list[bool]]
        | type[int]
        | type[list[int]]
        | type[np.uint64]
        | type[list[np.uint64]]
        | type[float]
        | type[list[float]]
        | type[timedelta]
        | type[list[timedelta]]
        | type[datetime]
        | type[list[datetime]]
        | type[UUID]
        | type[list[UUID]]
        | type[Geometry]
        | type[list[Geometry]]
    ]
    description: NotRequired[str]
    example_value: NotRequired[str]


_TYPE_INFO: dict[type, tuple[FieldDescriptorProto.Type.ValueType, str | None]] = {
    str: (FieldDescriptorProto.TYPE_STRING, None),
    bytes: (FieldDescriptorProto.TYPE_BYTES, None),
    bool: (FieldDescriptorProto.TYPE_BOOL, None),
    int: (FieldDescriptorProto.TYPE_INT64, None),
    np.uint64: (FieldDescriptorProto.TYPE_UINT64, None),
    float: (FieldDescriptorProto.TYPE_DOUBLE, None),
    timedelta: (FieldDescriptorProto.TYPE_MESSAGE, f".{duration_pb2.Duration.DESCRIPTOR.full_name}"),
    datetime: (FieldDescriptorProto.TYPE_MESSAGE, f".{timestamp_pb2.Timestamp.DESCRIPTOR.full_name}"),
    UUID: (FieldDescriptorProto.TYPE_MESSAGE, f".{well_known_types_pb2.UUID.DESCRIPTOR.full_name}"),
    Geometry: (FieldDescriptorProto.TYPE_MESSAGE, f".{well_known_types_pb2.Geometry.DESCRIPTOR.full_name}"),
}


@dataclass(frozen=True)
class Field:
    descriptor: FieldDescriptorProto
    annotation: FieldAnnotation
    queryable: bool

    @classmethod
    def from_message(cls, field: dataset_type_pb2.Field) -> "Field":
        return cls(
            descriptor=field.descriptor,
            annotation=FieldAnnotation.from_message(field.annotation),
            queryable=field.queryable,
        )

    @classmethod
    def from_dict(cls, field: FieldDict) -> "Field":
        origin = get_origin(field["type"])
        if origin is list:
            label = FieldDescriptorProto.Label.LABEL_REPEATED
            args = get_args(field["type"])
            inner_type = args[0] if args else field["type"]
        else:
            label = FieldDescriptorProto.Label.LABEL_OPTIONAL
            inner_type = field["type"]

        (field_type, field_type_name) = _TYPE_INFO[inner_type]

        return cls(
            descriptor=FieldDescriptorProto(
                name=field["name"],
                type=field_type,
                type_name=field_type_name,
                label=label,
            ),
            annotation=FieldAnnotation(
                description=field.get("description", ""),
                example_value=field.get("example_value", ""),
            ),
            queryable=False,
        )

    def to_message(self) -> dataset_type_pb2.Field:
        return dataset_type_pb2.Field(
            descriptor=self.descriptor,
            annotation=self.annotation.to_message(),
            queryable=self.queryable,
        )


@dataclass(frozen=True)
class DatasetType:
    kind: DatasetKind | None
    fields: list[Field]

    @classmethod
    def from_message(cls, dataset_type: dataset_type_pb2.DatasetType) -> "DatasetType":
        return cls(
            kind=_dataset_kind_int_to_enum.get(dataset_type.kind, None),
            fields=[Field.from_message(f) for f in dataset_type.fields],
        )

    def to_message(self) -> dataset_type_pb2.DatasetType:
        return dataset_type_pb2.DatasetType(
            kind=self.kind.value if self.kind else dataset_type_pb2.DATASET_KIND_UNSPECIFIED,
            fields=[f.to_message() for f in self.fields],
        )


@dataclass(frozen=True)
class AnnotatedType:
    descriptor_set: FileDescriptorSet
    type_url: str
    field_annotations: list[FieldAnnotation]

    @classmethod
    def from_message(cls, annotated_type: dataset_type_pb2.AnnotatedType) -> "AnnotatedType":
        return cls(
            descriptor_set=annotated_type.descriptor_set,
            type_url=annotated_type.type_url,
            field_annotations=[FieldAnnotation.from_message(a) for a in annotated_type.field_annotations],
        )

    def to_message(self) -> dataset_type_pb2.AnnotatedType:
        return dataset_type_pb2.AnnotatedType(
            descriptor_set=self.descriptor_set,
            type_url=self.type_url,
            field_annotations=[a.to_message() for a in self.field_annotations],
        )


@dataclass(frozen=True)
class Dataset:
    """Basic properties of a dataset."""

    id: UUID
    group_id: UUID
    type: AnnotatedType
    code_name: str
    name: str
    summary: str
    icon: str
    description: str

    @classmethod
    def from_message(cls, dataset: core_pb2.Dataset) -> "Dataset":
        return cls(
            id=uuid_message_to_uuid(dataset.id),
            group_id=uuid_message_to_uuid(dataset.group_id),
            type=AnnotatedType.from_message(dataset.type),
            code_name=dataset.code_name,
            name=dataset.name,
            summary=dataset.summary,
            icon=dataset.icon,
            description=dataset.description,
        )

    def to_message(self) -> core_pb2.Dataset:
        return core_pb2.Dataset(
            id=uuid_to_uuid_message(self.id),
            group_id=uuid_to_uuid_message(self.group_id),
            type=self.type.to_message(),
            code_name=self.code_name,
            name=self.name,
            summary=self.summary,
            icon=self.icon,
            description=self.description,
        )


@dataclass
class DatasetGroup:
    id: UUID
    parent_id: UUID | None
    code_name: str
    name: str
    icon: str

    @classmethod
    def from_message(cls, group: core_pb2.DatasetGroup) -> "DatasetGroup":
        return cls(
            id=uuid_message_to_uuid(group.id),
            parent_id=uuid_message_to_optional_uuid(group.parent_id),
            code_name=group.code_name,
            name=group.name,
            icon=group.icon,
        )

    def to_message(self) -> core_pb2.DatasetGroup:
        return core_pb2.DatasetGroup(
            id=uuid_to_uuid_message(self.id),
            parent_id=uuid_to_uuid_message(self.parent_id),
            code_name=self.code_name,
            name=self.name,
            icon=self.icon,
        )


@dataclass
class ListDatasetsResponse:
    datasets: list[Dataset]
    groups: list[DatasetGroup]
    server_message: str | None

    @classmethod
    def from_message(cls, response: datasets_pb2.ListDatasetsResponse) -> "ListDatasetsResponse":
        return cls(
            datasets=[Dataset.from_message(dataset) for dataset in response.datasets],
            groups=[DatasetGroup.from_message(group) for group in response.groups],
            server_message=response.server_message,
        )

    def to_message(self) -> datasets_pb2.ListDatasetsResponse:
        return datasets_pb2.ListDatasetsResponse(
            datasets=[dataset.to_message() for dataset in self.datasets],
            groups=[group.to_message() for group in self.groups],
            server_message=self.server_message,
        )
