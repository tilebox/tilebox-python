from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime, timedelta
from enum import Enum
from typing import Literal, NotRequired, Required, TypeAlias, TypedDict, get_args, get_origin

import numpy as np
from protobuf.wkt.google.protobuf import duration_pb, timestamp_pb
from protobuf.wkt.google.protobuf.descriptor_pb import FieldDescriptorProto, FileDescriptorSet

from tilebox.datasets.schema import UUID, Geometry, MessageFieldType, _message_field_type
from tilebox.datasets.uuid import uuid_message_to_optional_uuid, uuid_message_to_uuid, uuid_to_uuid_message
from tilebox.datasets.v1 import core_pb, dataset_type_pb, datasets_pb, well_known_types_pb


class DatasetKind(Enum):
    TEMPORAL = dataset_type_pb.DatasetKind.TEMPORAL
    """A dataset that contains a timestamp field."""
    SPATIOTEMPORAL = dataset_type_pb.DatasetKind.SPATIOTEMPORAL
    """A dataset that contains a timestamp field and a geometry field."""


_dataset_kind_int_to_enum = {kind.value: kind for kind in DatasetKind}


class FieldRole(Enum):
    PRIMARY_TITLE = dataset_type_pb.FieldRole.PRIMARY_TITLE
    """The primary human-readable title or name used when displaying a datapoint."""


_field_roles_from_string = {role.name.lower(): role for role in FieldRole}
_field_role_int_to_enum = {role.value: role for role in FieldRole}
FieldRolesLike: TypeAlias = list[FieldRole] | list[Literal["primary_title"]]


@dataclass(frozen=True)
class FieldAnnotation:
    description: str
    """A human-readable description of the field."""
    example_value: str
    """An example value illustrating the field's expected contents."""
    source_json_pointer: str | None = None
    """An RFC 6901 JSON Pointer locating the field value in the source document."""
    queryable: bool = False
    """Whether the field is available for use in server-side filter expressions."""
    json_schema_ref: str | None = None
    """A JSON Schema reference for the field when it corresponds to a well-known schema."""
    roles: list[FieldRole] = dataclass_field(default_factory=list)
    """Semantic display roles fulfilled by the field."""

    @classmethod
    def from_message(cls, annotation: dataset_type_pb.FieldAnnotation | None) -> "FieldAnnotation":
        if annotation is None:
            return cls("", "")
        return cls(
            description=annotation.description,
            example_value=annotation.example_value,
            source_json_pointer=annotation.source_json_pointer if annotation.has_field("source_json_pointer") else None,
            queryable=annotation.queryable,
            json_schema_ref=annotation.json_schema_ref if annotation.has_field("json_schema_ref") else None,
            roles=[_field_role_int_to_enum[role] for role in annotation.roles],
        )

    def to_message(self) -> dataset_type_pb.FieldAnnotation:
        annotation = dataset_type_pb.FieldAnnotation(
            description=self.description,
            example_value=self.example_value,
            queryable=self.queryable,
            roles=[role.value for role in self.roles],
        )
        if self.source_json_pointer is not None:
            annotation.source_json_pointer = self.source_json_pointer
        if self.json_schema_ref is not None:
            annotation.json_schema_ref = self.json_schema_ref
        return annotation


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
        | MessageFieldType
    ]
    description: NotRequired[str]
    example_value: NotRequired[str]
    source_json_pointer: NotRequired[str | None]
    queryable: NotRequired[bool]
    json_schema_ref: NotRequired[str | None]
    roles: NotRequired[FieldRolesLike]


_TYPE_INFO: dict[type, tuple[FieldDescriptorProto.Type, str | None]] = {
    str: (FieldDescriptorProto.Type.STRING, None),
    bytes: (FieldDescriptorProto.Type.BYTES, None),
    bool: (FieldDescriptorProto.Type.BOOL, None),
    int: (FieldDescriptorProto.Type.INT64, None),
    np.uint64: (FieldDescriptorProto.Type.UINT64, None),
    float: (FieldDescriptorProto.Type.DOUBLE, None),
    timedelta: (FieldDescriptorProto.Type.MESSAGE, f".{duration_pb.Duration.desc().type_name}"),
    datetime: (FieldDescriptorProto.Type.MESSAGE, f".{timestamp_pb.Timestamp.desc().type_name}"),
    UUID: (FieldDescriptorProto.Type.MESSAGE, f".{well_known_types_pb.UUID.desc().type_name}"),
    Geometry: (FieldDescriptorProto.Type.MESSAGE, f".{well_known_types_pb.Geometry.desc().type_name}"),
}


@dataclass(frozen=True)
class Field:
    descriptor: FieldDescriptorProto
    annotation: FieldAnnotation

    @classmethod
    def from_message(cls, field: dataset_type_pb.Field) -> "Field":
        if field.descriptor is None:
            raise ValueError("Dataset field is missing its descriptor")
        return cls(
            descriptor=field.descriptor,
            annotation=FieldAnnotation.from_message(field.annotation),
        )

    @classmethod
    def from_dict(cls, field: FieldDict) -> "Field":
        origin = get_origin(field["type"])
        if origin is list:
            label = FieldDescriptorProto.Label.REPEATED
            args = get_args(field["type"])
            inner_type = args[0] if args else field["type"]
        else:
            label = FieldDescriptorProto.Label.OPTIONAL
            inner_type = field["type"]

        message_type = _message_field_type(inner_type)
        if message_type is not None:
            field_type = FieldDescriptorProto.Type.MESSAGE
            field_type_name = f".{message_type.desc().type_name}"
        else:
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
                source_json_pointer=field.get("source_json_pointer"),
                queryable=field.get("queryable", False),
                json_schema_ref=field.get("json_schema_ref"),
                roles=[
                    _field_roles_from_string[role] if isinstance(role, str) else role for role in field.get("roles", [])
                ],
            ),
        )

    def to_message(self) -> dataset_type_pb.Field:
        return dataset_type_pb.Field(
            descriptor=self.descriptor,
            annotation=self.annotation.to_message(),
        )


@dataclass(frozen=True)
class DatasetType:
    kind: DatasetKind | None
    fields: list[Field]

    @classmethod
    def from_fields(cls, kind: DatasetKind, custom_fields: list[FieldDict]) -> "DatasetType":
        """Build a dataset schema with required metadata before custom fields."""
        return cls(kind, _REQUIRED_FIELDS_PER_DATASET_KIND[kind] + [Field.from_dict(field) for field in custom_fields])

    @classmethod
    def from_message(cls, dataset_type: dataset_type_pb.DatasetType) -> "DatasetType":
        return cls(
            kind=_dataset_kind_int_to_enum.get(dataset_type.kind),
            fields=[Field.from_message(f) for f in dataset_type.fields],
        )

    def to_message(self) -> dataset_type_pb.DatasetType:
        return dataset_type_pb.DatasetType(
            kind=self.kind.value if self.kind else dataset_type_pb.DatasetKind.UNSPECIFIED,
            fields=[f.to_message() for f in self.fields],
        )


_time_field = Field(
    descriptor=FieldDescriptorProto(
        name="time",
        label=FieldDescriptorProto.Label.OPTIONAL,
        type=FieldDescriptorProto.Type.MESSAGE,
        type_name=".google.protobuf.Timestamp",
    ),
    annotation=FieldAnnotation(
        description="The timestamp associated with each data point.",
        example_value="2022-10-17T14:35:28Z",
        source_json_pointer="/properties/datetime",
        json_schema_ref="https://schemas.stacspec.org/v1.1.0/item-spec/json-schema/datetime.json#/properties/datetime",
    ),
)
_id_field = Field(
    descriptor=FieldDescriptorProto(
        name="id",
        label=FieldDescriptorProto.Label.OPTIONAL,
        type=FieldDescriptorProto.Type.MESSAGE,
        type_name=".datasets.v1.UUID",
    ),
    annotation=FieldAnnotation(
        description="A universally unique identifier (UUID) that uniquely identifies each data point, automatically generated by Tilebox.",
        example_value="4e8a2836-72f8-4ac2-a9e9-cbe3492ef60c",
        source_json_pointer="/properties/tilebox:id",
    ),
)
_ingestion_time_field = Field(
    descriptor=FieldDescriptorProto(
        name="ingestion_time",
        label=FieldDescriptorProto.Label.OPTIONAL,
        type=FieldDescriptorProto.Type.MESSAGE,
        type_name=".google.protobuf.Timestamp",
    ),
    annotation=FieldAnnotation(
        description="The time the data point was ingested into the Tilebox API, automatically generated by Tilebox.",
        example_value="2022-10-17T14:35:28Z",
        source_json_pointer="/properties/tilebox:ingestion_time",
    ),
)
_geometry_field = Field(
    descriptor=FieldDescriptorProto(
        name="geometry",
        label=FieldDescriptorProto.Label.OPTIONAL,
        type=FieldDescriptorProto.Type.MESSAGE,
        type_name=".datasets.v1.Geometry",
    ),
    annotation=FieldAnnotation(
        description="The geometry associated with each data point.",
        example_value="POLYGON ((112.345 -36.789, ...))",
        source_json_pointer="/geometry",
        json_schema_ref="https://geojson.org/schema/Geometry.json",
    ),
)
_REQUIRED_FIELDS_PER_DATASET_KIND: dict[DatasetKind, list[Field]] = {
    DatasetKind.TEMPORAL: [_time_field, _id_field, _ingestion_time_field],
    DatasetKind.SPATIOTEMPORAL: [_time_field, _id_field, _ingestion_time_field, _geometry_field],
}


@dataclass(frozen=True)
class AnnotatedType:
    descriptor_set: FileDescriptorSet
    type_url: str
    field_annotations: list[FieldAnnotation]
    kind: DatasetKind | None = None

    @classmethod
    def from_message(cls, annotated_type: dataset_type_pb.AnnotatedType) -> "AnnotatedType":
        if annotated_type.descriptor_set is None:
            raise ValueError("Dataset type is missing its descriptor set")
        return cls(
            descriptor_set=annotated_type.descriptor_set,
            type_url=annotated_type.type_url,
            field_annotations=[FieldAnnotation.from_message(a) for a in annotated_type.field_annotations],
            kind=_dataset_kind_int_to_enum.get(annotated_type.kind),
        )

    def to_message(self) -> dataset_type_pb.AnnotatedType:
        return dataset_type_pb.AnnotatedType(
            descriptor_set=self.descriptor_set,
            type_url=self.type_url,
            field_annotations=[a.to_message() for a in self.field_annotations],
            kind=self.kind.value if self.kind else dataset_type_pb.DatasetKind.UNSPECIFIED,
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
    def from_message(cls, dataset: core_pb.Dataset) -> "Dataset":
        if dataset.type is None:
            raise ValueError("Dataset is missing its type")
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

    def to_message(self) -> core_pb.Dataset:
        return core_pb.Dataset(
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
    def from_message(cls, group: core_pb.DatasetGroup) -> "DatasetGroup":
        return cls(
            id=uuid_message_to_uuid(group.id),
            parent_id=uuid_message_to_optional_uuid(group.parent_id),
            code_name=group.code_name,
            name=group.name,
            icon=group.icon,
        )

    def to_message(self) -> core_pb.DatasetGroup:
        return core_pb.DatasetGroup(
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
    def from_message(cls, response: datasets_pb.ListDatasetsResponse) -> "ListDatasetsResponse":
        return cls(
            datasets=[Dataset.from_message(dataset) for dataset in response.datasets],
            groups=[DatasetGroup.from_message(group) for group in response.groups],
            server_message=response.server_message,
        )

    def to_message(self) -> datasets_pb.ListDatasetsResponse:
        return datasets_pb.ListDatasetsResponse(
            datasets=[dataset.to_message() for dataset in self.datasets],
            groups=[group.to_message() for group in self.groups],
            server_message=self.server_message or "",
        )
