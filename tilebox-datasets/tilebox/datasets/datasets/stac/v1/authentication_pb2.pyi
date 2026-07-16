from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class KnownAuthenticationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KNOWN_AUTHENTICATION_TYPE_UNSPECIFIED: _ClassVar[KnownAuthenticationType]
    KNOWN_AUTHENTICATION_TYPE_HTTP: _ClassVar[KnownAuthenticationType]
    KNOWN_AUTHENTICATION_TYPE_S3: _ClassVar[KnownAuthenticationType]
    KNOWN_AUTHENTICATION_TYPE_SIGNED_URL: _ClassVar[KnownAuthenticationType]
    KNOWN_AUTHENTICATION_TYPE_OAUTH2: _ClassVar[KnownAuthenticationType]
    KNOWN_AUTHENTICATION_TYPE_API_KEY: _ClassVar[KnownAuthenticationType]
    KNOWN_AUTHENTICATION_TYPE_OPEN_ID_CONNECT: _ClassVar[KnownAuthenticationType]
KNOWN_AUTHENTICATION_TYPE_UNSPECIFIED: KnownAuthenticationType
KNOWN_AUTHENTICATION_TYPE_HTTP: KnownAuthenticationType
KNOWN_AUTHENTICATION_TYPE_S3: KnownAuthenticationType
KNOWN_AUTHENTICATION_TYPE_SIGNED_URL: KnownAuthenticationType
KNOWN_AUTHENTICATION_TYPE_OAUTH2: KnownAuthenticationType
KNOWN_AUTHENTICATION_TYPE_API_KEY: KnownAuthenticationType
KNOWN_AUTHENTICATION_TYPE_OPEN_ID_CONNECT: KnownAuthenticationType

class Authentication(_message.Message):
    __slots__ = ("schemes",)
    class SchemesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: AuthenticationScheme
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[AuthenticationScheme, _Mapping]] = ...) -> None: ...
    SCHEMES_FIELD_NUMBER: _ClassVar[int]
    schemes: _containers.MessageMap[str, AuthenticationScheme]
    def __init__(self, schemes: _Optional[_Mapping[str, AuthenticationScheme]] = ...) -> None: ...

class AuthenticationScheme(_message.Message):
    __slots__ = ("known_type", "custom_type", "description", "name", "location", "scheme", "flows", "open_id_connect_url")
    KNOWN_TYPE_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_TYPE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SCHEME_FIELD_NUMBER: _ClassVar[int]
    FLOWS_FIELD_NUMBER: _ClassVar[int]
    OPEN_ID_CONNECT_URL_FIELD_NUMBER: _ClassVar[int]
    known_type: KnownAuthenticationType
    custom_type: str
    description: str
    name: str
    location: str
    scheme: str
    flows: _containers.RepeatedCompositeFieldContainer[AuthenticationFlow]
    open_id_connect_url: str
    def __init__(self, known_type: _Optional[_Union[KnownAuthenticationType, str]] = ..., custom_type: _Optional[str] = ..., description: _Optional[str] = ..., name: _Optional[str] = ..., location: _Optional[str] = ..., scheme: _Optional[str] = ..., flows: _Optional[_Iterable[_Union[AuthenticationFlow, _Mapping]]] = ..., open_id_connect_url: _Optional[str] = ...) -> None: ...

class AuthenticationFlow(_message.Message):
    __slots__ = ("key", "oauth2", "signed_url")
    KEY_FIELD_NUMBER: _ClassVar[int]
    OAUTH2_FIELD_NUMBER: _ClassVar[int]
    SIGNED_URL_FIELD_NUMBER: _ClassVar[int]
    key: str
    oauth2: OAuth2Flow
    signed_url: SignedURLFlow
    def __init__(self, key: _Optional[str] = ..., oauth2: _Optional[_Union[OAuth2Flow, _Mapping]] = ..., signed_url: _Optional[_Union[SignedURLFlow, _Mapping]] = ...) -> None: ...

class OAuth2Flow(_message.Message):
    __slots__ = ("authorization_url", "token_url", "scopes", "refresh_url")
    class ScopesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    AUTHORIZATION_URL_FIELD_NUMBER: _ClassVar[int]
    TOKEN_URL_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    REFRESH_URL_FIELD_NUMBER: _ClassVar[int]
    authorization_url: str
    token_url: str
    scopes: _containers.ScalarMap[str, str]
    refresh_url: str
    def __init__(self, authorization_url: _Optional[str] = ..., token_url: _Optional[str] = ..., scopes: _Optional[_Mapping[str, str]] = ..., refresh_url: _Optional[str] = ...) -> None: ...

class SignedURLFlow(_message.Message):
    __slots__ = ("method", "authorization_api", "parameters", "response_field")
    class ParametersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: AuthenticationParameter
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[AuthenticationParameter, _Mapping]] = ...) -> None: ...
    METHOD_FIELD_NUMBER: _ClassVar[int]
    AUTHORIZATION_API_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_FIELD_NUMBER: _ClassVar[int]
    method: str
    authorization_api: str
    parameters: _containers.MessageMap[str, AuthenticationParameter]
    response_field: str
    def __init__(self, method: _Optional[str] = ..., authorization_api: _Optional[str] = ..., parameters: _Optional[_Mapping[str, AuthenticationParameter]] = ..., response_field: _Optional[str] = ...) -> None: ...

class AuthenticationParameter(_message.Message):
    __slots__ = ("location", "required", "description", "schema")
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SCHEMA_FIELD_NUMBER: _ClassVar[int]
    location: str
    required: bool
    description: str
    schema: JSONSchema
    def __init__(self, location: _Optional[str] = ..., required: bool = ..., description: _Optional[str] = ..., schema: _Optional[_Union[JSONSchema, _Mapping]] = ...) -> None: ...

class JSONSchema(_message.Message):
    __slots__ = ("object", "boolean")
    OBJECT_FIELD_NUMBER: _ClassVar[int]
    BOOLEAN_FIELD_NUMBER: _ClassVar[int]
    object: _struct_pb2.Struct
    boolean: bool
    def __init__(self, object: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., boolean: bool = ...) -> None: ...
