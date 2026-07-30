"""Immutable models inspired by the STAC authentication extension.

See https://github.com/stac-extensions/authentication.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tilebox.datasets.assets.converters import converters
from tilebox.datasets.datasets.stac.v1.authentication_pb2 import AuthenticationParameter as ParameterProto
from tilebox.datasets.datasets.stac.v1.authentication_pb2 import AuthenticationScheme as SchemeProto
from tilebox.datasets.datasets.stac.v1.authentication_pb2 import OAuth2Flow as OAuth2FlowProto
from tilebox.datasets.datasets.stac.v1.authentication_pb2 import SignedURLFlow as SignedURLFlowProto


@converters.register(OAuth2FlowProto)
@dataclass(frozen=True, slots=True)
class OAuth2Flow:
    authorization_url: str | None = None
    token_url: str | None = None
    scopes: Mapping[str, str] = MappingProxyType({})
    refresh_url: str | None = None


@converters.register(ParameterProto)
@dataclass(frozen=True, slots=True)
class AuthenticationParameter:
    location: str | None = None
    required: bool | None = None
    description: str | None = None
    schema: Mapping[str, Any] = MappingProxyType({})


@converters.register(SignedURLFlowProto)
@dataclass(frozen=True, slots=True)
class SignedURLFlow:
    method: str | None = None
    authorization_api: str | None = None
    parameters: Mapping[str, AuthenticationParameter] = MappingProxyType({})
    response_field: str | None = None


def _convert_flows(flows: Any) -> Mapping[str, OAuth2Flow] | Mapping[str, SignedURLFlow]:
    oauth2_flows: dict[str, OAuth2Flow] = {}
    signed_url_flows: dict[str, SignedURLFlow] = {}
    for flow in flows:
        choices = [name for name in ("oauth2", "signed_url") if flow.HasField(name)]
        if len(choices) != 1:
            raise ValueError(f"authentication flow {flow.key!r} must define exactly one flow type")
        if flow.key in oauth2_flows or flow.key in signed_url_flows:
            raise ValueError(f"duplicate authentication flow key: {flow.key!r}")
        converted = converters.convert(getattr(flow, choices[0]))
        if isinstance(converted, OAuth2Flow):
            oauth2_flows[flow.key] = converted
        else:
            signed_url_flows[flow.key] = converted
    if oauth2_flows and signed_url_flows:
        raise ValueError("authentication scheme cannot mix OAuth2 and signed URL flows")
    return MappingProxyType(oauth2_flows) if oauth2_flows else MappingProxyType(signed_url_flows)


@converters.register(
    SchemeProto,
    rename_fields={"known_type": "type", "custom_type": "type"},
    field_converters={"flows": _convert_flows},
)
@dataclass(frozen=True, slots=True)
class AuthenticationScheme:
    key: str = ""
    type: str | None = None
    description: str | None = None
    name: str | None = None
    location: str | None = None
    scheme: str | None = None
    flows: Mapping[str, OAuth2Flow] | Mapping[str, SignedURLFlow] = MappingProxyType({})
    open_id_connect_url: str | None = None
