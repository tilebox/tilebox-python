from hypothesis import given

from tests.data.datasets import annotated_types, dataset_groups, datasets, field_annotations, list_datasets_responses
from tilebox.datasets.data.datasets import AnnotatedType, Dataset, DatasetGroup, FieldAnnotation, ListDatasetsResponse


@given(field_annotations())
def test_field_annotations_to_message_and_back(annotation: FieldAnnotation) -> None:
    assert FieldAnnotation.from_message(annotation.to_message()) == annotation


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
