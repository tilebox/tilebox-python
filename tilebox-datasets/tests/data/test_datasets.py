from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from hypothesis import given

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
from tilebox.datasets.service import TileboxDatasetService


@given(field_annotations())
def test_field_annotations_to_message_and_back(annotation: FieldAnnotation) -> None:
    assert FieldAnnotation.from_message(annotation.to_message()) == annotation


@pytest.mark.parametrize("attribute", ["source_json_pointer", "json_schema_ref"])
def test_optional_field_annotation_presence(attribute: str) -> None:
    absent = FieldAnnotation("description", "example").to_message()
    assert not absent.HasField(attribute)

    if attribute == "source_json_pointer":
        present = FieldAnnotation("description", "example", source_json_pointer="").to_message()
    else:
        present = FieldAnnotation("description", "example", json_schema_ref="").to_message()
    assert present.HasField(attribute)


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
def test_create_and_update_dataset_include_field_annotations(operation: str) -> None:
    dataset_service = MagicMock()
    service = TileboxDatasetService(dataset_service, MagicMock(), MagicMock(), MagicMock())
    custom_fields: list[FieldDict] = [
        {
            "name": "title",
            "type": str,
            "source_json_pointer": "/properties/title",
            "queryable": True,
            "json_schema_ref": "https://example.com/schema.json#/title",
            "roles": [FieldRole.PRIMARY_TITLE],
        }
    ]

    with patch.object(Dataset, "from_message", side_effect=lambda message: message):
        if operation == "create":
            service.create_dataset(DatasetKind.SPATIOTEMPORAL, "example", "Example", custom_fields).get()
            request = dataset_service.CreateDataset.call_args.args[0]
        else:
            service.update_dataset(DatasetKind.SPATIOTEMPORAL, uuid4(), "Example", custom_fields).get()
            request = dataset_service.UpdateDataset.call_args.args[0]

    annotations = {field.descriptor.name: field.annotation for field in request.type.fields}
    assert annotations["time"].source_json_pointer == "/properties/datetime"
    assert annotations["time"].json_schema_ref.endswith("datetime.json#/properties/datetime")
    assert annotations["id"].source_json_pointer == "/properties/tilebox_id"
    assert not annotations["id"].HasField("json_schema_ref")
    assert annotations["ingestion_time"].source_json_pointer == "/properties/created"
    assert annotations["ingestion_time"].json_schema_ref.endswith("datetime.json#/properties/created")
    assert annotations["geometry"].source_json_pointer == "/geometry"
    assert annotations["geometry"].json_schema_ref == "https://geojson.org/schema/Geometry.json"
    assert all(
        not annotation.queryable and not annotation.roles for name, annotation in annotations.items() if name != "title"
    )
    assert annotations["title"].source_json_pointer == "/properties/title"
    assert annotations["title"].queryable
    assert annotations["title"].json_schema_ref == "https://example.com/schema.json#/title"
    assert list(annotations["title"].roles) == [FieldRole.PRIMARY_TITLE.value]
