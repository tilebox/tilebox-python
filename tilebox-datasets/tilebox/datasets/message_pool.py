"""Load isolated native schemas, including the imports supported by datasets."""

from functools import lru_cache

from protobuf import Message, Registry
from protobuf._codegen import file_desc
from protobuf.wkt.google.protobuf import descriptor_pb, duration_pb, timestamp_pb

from _tilebox.proto.tilebox.v1 import id_pb
from tilebox.datasets.data.datasets import AnnotatedType
from tilebox.datasets.stac.v1 import (
    asset_metadata_pb,
    asset_pb,
    authentication_pb,
    core_pb,
    processing_pb,
    product_pb,
    sar_pb,
    satellite_pb,
    storage_pb,
)
from tilebox.datasets.v1 import well_known_types_pb


@lru_cache(maxsize=1)
def _known_imports() -> Registry:
    return Registry(
        *(
            module.desc()
            for module in (
                descriptor_pb,
                duration_pb,
                timestamp_pb,
                id_pb,
                well_known_types_pb,
                asset_metadata_pb,
                asset_pb,
                authentication_pb,
                core_pb,
                processing_pb,
                product_pb,
                sar_pb,
                satellite_pb,
                storage_pb,
            )
        )
    )


@lru_cache(maxsize=128)
def _load(descriptor_content: bytes, type_url: str) -> type[Message]:
    supplied = descriptor_pb.FileDescriptorSet.from_binary(descriptor_content)
    files = {file.name: file for file in supplied.file}
    registry = Registry(_known_imports())
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"Cyclic descriptor dependency: {name}")
        file = files.get(name)
        if file is None:
            if registry.file(name) is None:
                raise ValueError(f"Unknown descriptor dependency: {name}")
            return
        visiting.add(name)
        for dependency in file.dependency:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        dependencies = []
        for dependency in file.dependency:
            descriptor = registry.file(dependency)
            assert descriptor is not None
            dependencies.append(descriptor)
        registry.add(file_desc(file.to_binary(), dependencies, {}))

    for name in files:
        visit(name)
    descriptor = registry.message(type_url.rsplit("/", 1)[-1].removeprefix("."))
    if descriptor is None:
        raise ValueError(f"Message type not found in descriptor set: {type_url}")
    return descriptor.type


def get_message_type(message_type: AnnotatedType) -> type[Message]:
    """Resolve the native class cached by descriptor content and type name."""
    type_name = message_type.type_url.rsplit("/", 1)[-1].removeprefix(".")
    return _load(message_type.descriptor_set.to_binary(), type_name)
