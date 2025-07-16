from dataclasses import dataclass
from uuid import UUID

from google.protobuf.descriptor_pb2 import FileDescriptorSet

from tilebox.datasets.datasets.v1 import core_pb2, dataset_type_pb2, datasets_pb2
from tilebox.datasets.uuid import uuid_message_to_optional_uuid, uuid_message_to_uuid, uuid_to_uuid_message


@dataclass(frozen=True)
class FieldAnnotation:
    description: str
    example_value: str

    @classmethod
    def from_message(cls, annotation: dataset_type_pb2.FieldAnnotation) -> "FieldAnnotation":
        return cls(description=annotation.description, example_value=annotation.example_value)

    def to_message(self) -> dataset_type_pb2.FieldAnnotation:
        return dataset_type_pb2.FieldAnnotation(description=self.description, example_value=self.example_value)


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
