from collections.abc import Callable
from dataclasses import replace
from typing import Any, Literal, cast
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from hypothesis import given
from protobuf.wkt.google.protobuf.descriptor_pb import FieldDescriptorProto, FileDescriptorProto, FileDescriptorSet

from _tilebox.errors import NotFoundError
from tests.data.datasets import (
    annotated_types,
    dataset_groups,
    dataset_types,
    datasets,
    field_annotations,
    field_dicts,
    fields,
    list_datasets_responses,
)
from tests.example_dataset.schema import DESCRIPTOR
from tilebox.datasets import Client
from tilebox.datasets.data.collection import CollectionInfo
from tilebox.datasets.data.data_access import SpatialFilter
from tilebox.datasets.data.datasets import (
    AnnotatedType,
    Dataset,
    DatasetGroup,
    DatasetKind,
    DatasetType,
    Field,
    FieldAnnotation,
    FieldDict,
    FieldRole,
    ListDatasetsResponse,
)
from tilebox.datasets.message_pool import get_message_type
from tilebox.datasets.schema import Assets, Authentication, Links, ProcessingSoftware, Provider, Storage
from tilebox.datasets.v1 import core_pb, data_access_pb, dataset_type_pb


@given(field_annotations())
def test_field_annotations_to_message_and_back(annotation: FieldAnnotation) -> None:
    assert FieldAnnotation.from_message(annotation.to_message()) == annotation


def test_schema_cache_reuses_content_without_conflating_same_named_types() -> None:
    """Reuse equivalent schemas while isolating different descriptors with the same message name."""
    schema = AnnotatedType(FileDescriptorSet(file=[DESCRIPTOR]), "tests.scientific.Datapoint", [])
    original = get_message_type(schema)
    equivalent = AnnotatedType.from_message(schema.to_message())
    assert get_message_type(equivalent) is original
    assert get_message_type(replace(schema, type_url="type.googleapis.com/tests.scientific.Datapoint")) is original

    changed = FileDescriptorProto.from_binary(DESCRIPTOR.to_binary())
    changed.message_type[0].field[4].type = FieldDescriptorProto.Type.INT64
    other = get_message_type(replace(schema, descriptor_set=FileDescriptorSet(file=[changed])))
    assert other is not original
    field_name = changed.message_type[0].field[4].name
    assert getattr(original.from_binary(original(some_string="value").to_binary()), field_name) == "value"
    assert getattr(other.from_binary(other(some_string=42).to_binary()), field_name) == 42


@pytest.mark.parametrize(
    ("convert", "message", "error"),
    [
        (Field.from_message, dataset_type_pb.Field(), "missing its descriptor"),
        (AnnotatedType.from_message, dataset_type_pb.AnnotatedType(), "missing its descriptor set"),
        (Dataset.from_message, core_pb.Dataset(), "missing its type"),
        (CollectionInfo.from_message, core_pb.CollectionInfo(), "missing its collection"),
        (SpatialFilter.from_message, data_access_pb.SpatialFilter(), "missing its geometry"),
    ],
)
def test_required_nested_messages_are_rejected(convert: Callable[[Any], Any], message: Any, error: str) -> None:
    """Reject incomplete responses with a useful error instead of dereferencing absent messages."""
    with pytest.raises(ValueError, match=error):
        convert(message)


@pytest.mark.parametrize("attribute", ["source_json_pointer", "json_schema_ref"])
def test_optional_field_annotation_presence(attribute: Literal["source_json_pointer", "json_schema_ref"]) -> None:
    absent = FieldAnnotation("description", "example").to_message()
    assert not absent.has_field(attribute)

    if attribute == "source_json_pointer":
        present = FieldAnnotation("description", "example", source_json_pointer="").to_message()
    else:
        present = FieldAnnotation("description", "example", json_schema_ref="").to_message()
    assert present.has_field(attribute)
    assert getattr(present, attribute) == ""


@given(field_dicts())
def test_field_from_dict(field_dict: FieldDict) -> None:
    field = Field.from_dict(field_dict)
    assert field.descriptor.name == field_dict["name"]
    assert field.descriptor.type is not None
    assert field.annotation.description == field_dict.get("description", "")
    assert field.annotation.example_value == field_dict.get("example_value", "")
    assert field.annotation.source_json_pointer == field_dict.get("source_json_pointer")
    assert field.annotation.queryable == field_dict.get("queryable", False)
    assert field.annotation.json_schema_ref == field_dict.get("json_schema_ref")
    assert field.annotation.roles == [
        FieldRole[role.upper()] if isinstance(role, str) else role for role in field_dict.get("roles", [])
    ]


@pytest.mark.parametrize(
    ("message_type", "message_name"),
    [
        (Assets, "datasets.stac.v1.Assets"),
        (Authentication, "datasets.stac.v1.Authentication"),
        (Links, "datasets.stac.v1.Links"),
        (Provider, "datasets.stac.v1.Provider"),
        (ProcessingSoftware, "datasets.stac.v1.ProcessingSoftware"),
        (Storage, "datasets.stac.v1.Storage"),
    ],
)
def test_message_types_can_define_dataset_fields(message_type: type, message_name: str) -> None:
    scalar = Field.from_dict({"name": "metadata", "type": message_type})
    repeated = Field.from_dict({"name": "metadata", "type": list[message_type]})  # ty: ignore[invalid-type-form]

    assert scalar.descriptor.type == FieldDescriptorProto.Type.MESSAGE
    assert scalar.descriptor.type_name == f".{message_name}"
    assert scalar.descriptor.label == FieldDescriptorProto.Label.OPTIONAL
    assert repeated.descriptor.type_name == f".{message_name}"
    assert repeated.descriptor.label == FieldDescriptorProto.Label.REPEATED


@pytest.mark.parametrize(
    "definition",
    [
        {"type": "enum"},
        {"type": "enum", "enum_values": []},
        {"type": "enum", "enum_values": [""]},
        {"type": "enum", "enum_values": ["L1", "L1"]},
        {"type": "enum", "enum_values": [1]},
        {"type": "enum", "enum_values": "L1"},
        {"type": "enum", "enum_values": [str(i) for i in range(101)]},
        {"type": str, "repeated": True},
        {"type": str, "enum_values": []},
    ],
)
def test_invalid_enum_definitions(definition: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Field 'level'"):
        Field.from_dict(cast(FieldDict, {"name": "level", **definition}))


@pytest.mark.parametrize("repeated", [False, True])
def test_enum_vocabulary_limit(repeated: bool) -> None:
    values = [str(i) for i in range(100)]
    definition: FieldDict = {"name": "level", "type": "enum", "enum_values": values, "repeated": repeated}
    assert Field.from_dict(definition).annotation.enum_values == values
    values.append("100")
    with pytest.raises(ValueError, match="at most 100"):
        Field.from_dict(definition)


@given(fields())
def test_fields_to_message_and_back(field: Field) -> None:
    assert Field.from_message(field.to_message()) == field


@given(dataset_types())
def test_dataset_types_to_message_and_back(dataset_type: DatasetType) -> None:
    assert DatasetType.from_message(dataset_type.to_message()) == dataset_type


@given(annotated_types())
def test_annotated_types_to_message_and_back(annotated_type: AnnotatedType) -> None:
    assert AnnotatedType.from_message(annotated_type.to_message()) == annotated_type


@given(datasets())
def test_datasets_to_message_and_back(dataset: Dataset) -> None:
    assert Dataset.from_message(dataset.to_message()) == dataset


@given(dataset_groups())
def test_dataset_groups_to_message_and_back(group: DatasetGroup) -> None:
    assert DatasetGroup.from_message(group.to_message()) == group


@given(list_datasets_responses())
def test_list_datasets_responses_to_message_and_back(response: ListDatasetsResponse) -> None:
    assert ListDatasetsResponse.from_message(response.to_message()) == response


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("repeated", [False, True])
def test_create_and_update_dataset_include_field_annotations(operation: str, repeated: bool) -> None:
    """Public dataset writes send required and custom field annotations to native clients."""
    dataset_service = MagicMock()
    if operation == "create":
        dataset_service.get_dataset.side_effect = NotFoundError
    custom_fields: list[FieldDict] = [
        {
            "name": "title",
            "type": str,
            "source_json_pointer": "/properties/title",
            "queryable": True,
            "json_schema_ref": "https://example.com/schema.json#/title",
            "roles": [FieldRole.PRIMARY_TITLE],
        },
        {
            "name": "level",
            "type": "enum",
            "enum_values": ["L1", "L2-SP", "雪"],
            "queryable": True,
            "repeated": repeated,
        },
    ]

    with (
        patch("tilebox.datasets.sync.client.Connection") as connection,
        patch("tilebox.datasets.sync.client.DatasetClient"),
        patch.object(Dataset, "from_message", return_value=MagicMock(id=uuid4(), name="Example")),
    ):
        connection.return_value.client.return_value = dataset_service
        with Client(url="http://localhost", token="test") as client:  # noqa: S106
            client.create_or_update_dataset(DatasetKind.SPATIOTEMPORAL, "example", custom_fields, name="Example")
        request = getattr(dataset_service, f"{operation}_dataset").call_args.args[0]

    annotations = {field.descriptor.name: field.annotation for field in request.type.fields}
    assert annotations["time"].source_json_pointer == "/properties/datetime"
    assert annotations["time"].json_schema_ref.endswith("datetime.json#/properties/datetime")
    assert annotations["id"].source_json_pointer == "/properties/tilebox:id"
    assert not annotations["id"].has_field("json_schema_ref")
    assert annotations["ingestion_time"].source_json_pointer == "/properties/tilebox:ingestion_time"
    assert not annotations["ingestion_time"].has_field("json_schema_ref")
    assert annotations["geometry"].source_json_pointer == "/geometry"
    assert annotations["geometry"].json_schema_ref == "https://geojson.org/schema/Geometry.json"
    assert all(
        not annotation.queryable and not annotation.roles
        for name, annotation in annotations.items()
        if name not in {"title", "level"}
    )
    assert annotations["title"].source_json_pointer == "/properties/title"
    assert annotations["title"].queryable
    assert annotations["title"].json_schema_ref == "https://example.com/schema.json#/title"
    assert list(annotations["title"].roles) == [FieldRole.PRIMARY_TITLE.value]
    enum_field = request.type.fields[-1]
    assert enum_field.descriptor.type == FieldDescriptorProto.Type.ENUM
    assert enum_field.descriptor.label == (
        FieldDescriptorProto.Label.REPEATED if repeated else FieldDescriptorProto.Label.OPTIONAL
    )
    assert not enum_field.descriptor.type_name
    assert enum_field.annotation.queryable
    assert [entry.value for entry in enum_field.annotation.enum_values] == ["L1", "L2-SP", "雪"]
    assert all(field.descriptor.options is None for field in request.type.fields)
