import json

from protobuf import Message
from protobuf.wkt.google.protobuf.descriptor_pb import FieldDescriptorProto

from tilebox.datasets.data.datasets import Dataset
from tilebox.datasets.protobuf_conversion.field_types import enum_mapping_from_field_descriptor


def dataset_repr(dataset: Dataset, message_type: type[Message]) -> str:
    kind = dataset.type.kind
    label = f"{kind.name.title()} Dataset" if kind else "Dataset"
    heading = f"{dataset.name} [{label}]"
    if dataset.summary:
        heading += f": {dataset.summary}"
    lines = [dataset.slug or dataset.code_name, heading, "", "Fields:"]

    descriptor = message_type.desc()
    fields = descriptor.proto.field
    fields_by_name = {field.name: field for field in descriptor.fields}
    name_width = max((len(field.name) for field in fields), default=0)
    for index, field in enumerate(fields):
        annotation = dataset.type.field_annotations[index] if index < len(dataset.type.field_annotations) else None
        marker = {"time": "🕒", "id": "🔑"}.get(field.name, "🔍" if annotation and annotation.queryable else "  ")
        if field.type == FieldDescriptorProto.Type.ENUM:
            values = (
                annotation.enum_values
                if annotation and annotation.enum_values
                else enum_mapping_from_field_descriptor(fields_by_name[field.name]).values()
            )
            field_type = "enum (" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + ")"
        elif field.type == FieldDescriptorProto.Type.MESSAGE:
            field_type = field.type_name.rsplit(".", 1)[-1]
        else:
            field_type = field.type.name.lower()
        if field.label == FieldDescriptorProto.Label.REPEATED:
            field_type = f"[] {field_type}"
        lines.append(f"{marker}  {field.name:<{name_width}}  {field_type}")

    return "\n".join(lines)
