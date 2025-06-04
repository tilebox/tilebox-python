from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RenderDiagramRequest(_message.Message):
    __slots__ = ("diagram", "render_options")
    DIAGRAM_FIELD_NUMBER: _ClassVar[int]
    RENDER_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    diagram: str
    render_options: RenderOptions
    def __init__(self, diagram: _Optional[str] = ..., render_options: _Optional[_Union[RenderOptions, _Mapping]] = ...) -> None: ...

class RenderOptions(_message.Message):
    __slots__ = ("layout", "theme_id", "sketchy", "padding", "direction")
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    THEME_ID_FIELD_NUMBER: _ClassVar[int]
    SKETCHY_FIELD_NUMBER: _ClassVar[int]
    PADDING_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    layout: str
    theme_id: int
    sketchy: bool
    padding: int
    direction: str
    def __init__(self, layout: _Optional[str] = ..., theme_id: _Optional[int] = ..., sketchy: bool = ..., padding: _Optional[int] = ..., direction: _Optional[str] = ...) -> None: ...

class Diagram(_message.Message):
    __slots__ = ("svg",)
    SVG_FIELD_NUMBER: _ClassVar[int]
    svg: bytes
    def __init__(self, svg: _Optional[bytes] = ...) -> None: ...
