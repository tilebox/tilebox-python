import string
from dataclasses import replace
from datetime import datetime, timedelta
from functools import lru_cache
from uuid import UUID

import numpy as np
from google.protobuf.descriptor_pb2 import FieldDescriptorProto, FileDescriptorProto, FileDescriptorSet
from hypothesis.strategies import (
    DrawFn,
    booleans,
    composite,
    integers,
    just,
    lists,
    none,
    one_of,
    sampled_from,
    text,
    uuids,
)
from shapely import Geometry

from tests.example_dataset.example_dataset_pb2 import DESCRIPTOR_PROTO
from tilebox.datasets.data.datasets import (
    AnnotatedType,
    Dataset,
    DatasetGroup,
    DatasetKind,
    DatasetType,
    Field,
    FieldAnnotation,
    FieldDict,
    ListDatasetsResponse,
)
from tilebox.datasets.message_pool import register_once


@composite
def field_annotations(draw: DrawFn) -> FieldAnnotation:
    """A hypothesis strategy for generating random field annotations"""
    description = draw(text(alphabet=string.ascii_letters, min_size=3, max_size=25))
    example_value = draw(text(alphabet=string.ascii_letters + string.digits + "-_", min_size=1, max_size=10))
    return FieldAnnotation(description, example_value)


@composite
def field_dicts(draw: DrawFn) -> FieldDict:
    """A hypothesis strategy for generating random field dicts"""
    name = draw(text(alphabet=string.ascii_lowercase + "_", min_size=3, max_size=25))
    field_type = draw(
        one_of(
            just(str),
            just(list[str]),
            just(bytes),
            just(list[bytes]),
            just(bool),
            just(list[bool]),
            just(int),
            just(list[int]),
            just(np.uint64),
            just(list[np.uint64]),
            just(float),
            just(list[float]),
            just(timedelta),
            just(list[timedelta]),
            just(datetime),
            just(list[datetime]),
            just(UUID),
            just(list[UUID]),
            just(Geometry),
            just(list[Geometry]),
        )
    )
    annotation = draw(field_annotations())

    return {
        "name": name,
        "type": field_type,
        "description": annotation.description,
        "example_value": annotation.example_value,
    }


@composite
def fields(draw: DrawFn) -> Field:
    """A hypothesis strategy for generating random fields"""
    name = draw(text(alphabet=string.ascii_lowercase + "_", min_size=3, max_size=25))
    field_type = draw(
        one_of(
            just(FieldDescriptorProto.Type.TYPE_STRING),
            just(FieldDescriptorProto.Type.TYPE_BYTES),
            just(FieldDescriptorProto.Type.TYPE_BOOL),
            just(FieldDescriptorProto.Type.TYPE_INT64),
            just(FieldDescriptorProto.Type.TYPE_UINT64),
            just(FieldDescriptorProto.Type.TYPE_DOUBLE),
            just(FieldDescriptorProto.Type.TYPE_MESSAGE),
        )
    )
    type_name = f".datasets.v1.{name}" if field_type == FieldDescriptorProto.Type.TYPE_MESSAGE else None
    label = draw(
        one_of(just(FieldDescriptorProto.Label.LABEL_OPTIONAL), just(FieldDescriptorProto.Label.LABEL_REPEATED))
    )
    descriptor = FieldDescriptorProto(name=name, type=field_type, type_name=type_name, label=label)

    annotation = draw(field_annotations())
    queryable = draw(booleans())
    return Field(descriptor, annotation, queryable)


@composite
def dataset_types(draw: DrawFn) -> DatasetType:
    """A hypothesis strategy for generating random dataset types"""
    kind = draw(sampled_from(DatasetKind) | none())
    dataset_fields = draw(lists(fields(), min_size=1, max_size=5))
    return DatasetType(kind, dataset_fields)


@lru_cache
def example_dataset_type() -> AnnotatedType:
    descriptor = FileDescriptorProto.FromString(DESCRIPTOR_PROTO)
    # we deliberately change the package name to something other than the generated default, to simulate a protobuf
    # file that was sent from the server and is not actually available and already registered
    descriptor.name = "example_dynamic_dataset/v1/example_dynamic_dataset.proto"
    descriptor.package = "example_dynamic_dataset.v1"
    descriptor.message_type[0].name = "ExampleDynamicDatapoint"
    descriptor_set = FileDescriptorSet(file=[descriptor])

    type_url = f"{descriptor.package}.{descriptor.message_type[0].name}"
    annotated_type = AnnotatedType(descriptor_set, type_url, [])
    register_once(annotated_type)
    return annotated_type


@lru_cache
def example_dataset_type_url() -> str:
    return example_dataset_type().type_url


@composite
def annotated_types(draw: DrawFn) -> AnnotatedType:
    """A hypothesis strategy for generating random annotated types"""
    return draw(just(example_dataset_type()))  # right now we hardcode one protobuf type, see example_dataset.proto


@composite
def datasets(draw: DrawFn) -> Dataset:
    """A hypothesis strategy for generating random datasets"""
    dataset_id = draw(uuids(version=4))
    group_id = draw(uuids(version=4))
    dataset_type = draw(annotated_types())
    code_name = draw(text(alphabet=string.ascii_lowercase + "_", min_size=3, max_size=25))
    name = draw(text(alphabet=string.ascii_letters + string.digits + " -_", min_size=3, max_size=25))
    summary = draw(text(min_size=0, max_size=200))
    icon = draw(one_of(just("globe"), just("satellite")))
    description = draw(text())
    return Dataset(dataset_id, group_id, dataset_type, code_name, name, summary, icon, description)


@composite
def dataset_groups(draw: DrawFn) -> DatasetGroup:
    """A hypothesis strategy for generating random datasets"""
    dataset_id = draw(uuids(version=4))
    parent_id = draw(uuids(version=4) | none())
    code_name = draw(text(alphabet=string.ascii_lowercase + "_", min_size=3, max_size=25))
    name = draw(text(alphabet=string.ascii_letters + string.digits + " -_", min_size=3, max_size=25))
    icon = draw(one_of(just("globe"), just("satellite")))
    return DatasetGroup(dataset_id, parent_id, code_name, name, icon)


@composite
def list_datasets_responses(draw: DrawFn) -> ListDatasetsResponse:
    """A hypothesis strategy for generating random list datasets responses"""
    datasets_ = draw(lists(datasets(), min_size=3, max_size=5))
    groups = draw(lists(dataset_groups(), min_size=3, max_size=5))
    server_message = draw(text(min_size=0, max_size=200))

    # assign each dataset to one of the groups:
    for i, ds in enumerate(datasets_):
        group_index = draw(integers(min_value=0, max_value=len(groups) - 1))
        datasets_[i] = replace(ds, group_id=groups[group_index].id)

    # make groups possibly recursively nested:
    for i, group in enumerate(groups):
        # each group can possibly have one of the groups before it in the list as a parent
        # that way we can easily create a tree of groups without having cycles in the parent / child relationships
        parent_group = None if i == 0 else draw(integers(min_value=0, max_value=i) | none())
        groups[i] = replace(group, parent_id=None if parent_group is None else groups[parent_group].id)

    return ListDatasetsResponse(datasets_, groups, server_message)
