from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProductAcquisitionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRODUCT_ACQUISITION_TYPE_UNSPECIFIED: _ClassVar[ProductAcquisitionType]
    PRODUCT_ACQUISITION_TYPE_NOMINAL: _ClassVar[ProductAcquisitionType]
    PRODUCT_ACQUISITION_TYPE_CALIBRATION: _ClassVar[ProductAcquisitionType]
    PRODUCT_ACQUISITION_TYPE_OTHER: _ClassVar[ProductAcquisitionType]
PRODUCT_ACQUISITION_TYPE_UNSPECIFIED: ProductAcquisitionType
PRODUCT_ACQUISITION_TYPE_NOMINAL: ProductAcquisitionType
PRODUCT_ACQUISITION_TYPE_CALIBRATION: ProductAcquisitionType
PRODUCT_ACQUISITION_TYPE_OTHER: ProductAcquisitionType

class ProductProperties(_message.Message):
    __slots__ = ("type", "timeliness", "timeliness_category", "acquisition_type")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TIMELINESS_FIELD_NUMBER: _ClassVar[int]
    TIMELINESS_CATEGORY_FIELD_NUMBER: _ClassVar[int]
    ACQUISITION_TYPE_FIELD_NUMBER: _ClassVar[int]
    type: str
    timeliness: str
    timeliness_category: str
    acquisition_type: ProductAcquisitionType
    def __init__(self, type: _Optional[str] = ..., timeliness: _Optional[str] = ..., timeliness_category: _Optional[str] = ..., acquisition_type: _Optional[_Union[ProductAcquisitionType, str]] = ...) -> None: ...
