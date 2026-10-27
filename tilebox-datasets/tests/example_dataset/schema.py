"""Native descriptors for scientific conversion properties."""

from typing import TYPE_CHECKING, Any

from protobuf.wkt.google.protobuf.descriptor_pb import (
    DescriptorProto,
    Edition,
    FieldDescriptorProto,
    FileDescriptorProto,
    FileDescriptorSet,
)

from tilebox.datasets.data.datasets import AnnotatedType
from tilebox.datasets.message_pool import get_message_type

_T = FieldDescriptorProto.Type
_L = FieldDescriptorProto.Label
_FIELDS = [
    ("time", _T.MESSAGE, ".google.protobuf.Timestamp"),
    ("id", _T.MESSAGE, ".datasets.v1.UUID"),
    ("ingestion_time", _T.MESSAGE, ".google.protobuf.Timestamp"),
    ("geometry", _T.MESSAGE, ".datasets.v1.Geometry"),
    ("some_string", _T.STRING, None),
    ("some_int", _T.INT64, None),
    ("some_double", _T.DOUBLE, None),
    ("some_time", _T.MESSAGE, ".google.protobuf.Timestamp"),
    ("some_duration", _T.MESSAGE, ".google.protobuf.Duration"),
    ("some_bytes", _T.BYTES, None),
    ("some_bool", _T.BOOL, None),
    ("some_identifier", _T.MESSAGE, ".datasets.v1.UUID"),
    ("some_vec3", _T.MESSAGE, ".datasets.v1.Vec3"),
    ("some_quaternion", _T.MESSAGE, ".datasets.v1.Quaternion"),
    ("some_geometry", _T.MESSAGE, ".datasets.v1.Geometry"),
    ("some_enum", _T.ENUM, ".datasets.v1.ProcessingLevel"),
    ("some_repeated_string", _T.STRING, None),
    ("some_repeated_int", _T.INT64, None),
    ("some_repeated_double", _T.DOUBLE, None),
    ("some_repeated_bytes", _T.BYTES, None),
    ("some_repeated_bool", _T.BOOL, None),
    ("some_repeated_time", _T.MESSAGE, ".google.protobuf.Timestamp"),
    ("some_repeated_duration", _T.MESSAGE, ".google.protobuf.Duration"),
    ("some_repeated_identifier", _T.MESSAGE, ".datasets.v1.UUID"),
    ("some_repeated_vec3", _T.MESSAGE, ".datasets.v1.Vec3"),
    ("some_repeated_geometry", _T.MESSAGE, ".datasets.v1.Geometry"),
]

DESCRIPTOR = FileDescriptorProto(
    name="tests/example_dataset.proto",
    package="tests.scientific",
    syntax="editions",
    edition=Edition.EDITION_2023,
    dependency=[
        "datasets/v1/well_known_types.proto",
        "google/protobuf/timestamp.proto",
        "google/protobuf/duration.proto",
    ],
    message_type=[
        DescriptorProto(
            name="Datapoint",
            field=[
                FieldDescriptorProto(
                    name=name,
                    number=index,
                    type=kind,
                    type_name=type_name,
                    label=_L.REPEATED if "repeated" in name else _L.OPTIONAL,
                )
                for index, (name, kind, type_name) in enumerate(_FIELDS, start=1)
            ],
        )
    ],
)
DESCRIPTOR_PROTO = DESCRIPTOR.to_binary()
if TYPE_CHECKING:
    from protobuf import Message

    class ExampleDatapoint(Message):
        """Static shape for the descriptor-defined scientific fixture."""

        def __init__(self, **fields: Any) -> None: ...

        def __getattr__(self, name: str) -> Any: ...
else:
    ExampleDatapoint = get_message_type(
        AnnotatedType(FileDescriptorSet(file=[DESCRIPTOR]), "tests.scientific.Datapoint", [])
    )
