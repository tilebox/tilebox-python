from google.protobuf import descriptor_pb2, duration_pb2, timestamp_pb2
from google.protobuf.descriptor_pool import Default
from google.protobuf.message_factory import GetMessageClass, GetMessages

from tilebox.datasets.data.datasets import AnnotatedType
from tilebox.datasets.datasets.v1 import well_known_types_pb2

# make sure all the well known types are imported, and therefore available in the global protobuf message pool
__all__ = ["duration_pb2", "timestamp_pb2", "well_known_types_pb2"]  # this is here so ruff doesn't remove the imports


def register_once(message_type: AnnotatedType) -> type:
    try:
        # if it was already registered, we should be able to get if from the global message pool
        return get_message_type(message_type.type_url)
    except KeyError:
        # otherwise we need to register it
        register_message_types(message_type.descriptor_set)

    # but now we should be able to get it from the global message pool
    return get_message_type(message_type.type_url)


def register_message_types(descriptor_set: descriptor_pb2.FileDescriptorSet) -> None:
    GetMessages(descriptor_set.file, pool=Default())


def get_message_type(type_url: str) -> type:
    return GetMessageClass(Default().FindMessageTypeByName(type_url))
