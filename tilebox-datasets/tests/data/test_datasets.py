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
    DatasetType,
    Field,
    FieldAnnotation,
    FieldDict,
    ListDatasetsResponse,
)


@given(field_annotations())
def test_field_annotations_to_message_and_back(annotation: FieldAnnotation) -> None:
    assert FieldAnnotation.from_message(annotation.to_message()) == annotation


@given(field_dicts())
def test_field_from_dict(field_dict: FieldDict) -> None:
    field = Field.from_dict(field_dict)
    assert field.descriptor.name == field_dict["name"]
    assert field.descriptor.type is not None
    assert field.annotation.description == field_dict.get("description", "")
    assert field.annotation.example_value == field_dict.get("example_value", "")


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
