from unittest.mock import AsyncMock

import pytest

from _tilebox.grpc.aio.channel import ClientCallDetails, _AuthMetadataInterceptor, _RpcMethodPrefixInterceptor


@pytest.mark.asyncio
@pytest.mark.parametrize("req_metadata", [None, [("some-other", "header")]])
async def test_auth_interceptor(req_metadata: None | list[tuple[str, str]]) -> None:
    """Test that the auth interceptor adds the auth token as metadata to every gRPC request"""
    interceptor = _AuthMetadataInterceptor("very-secret")

    mock_method = AsyncMock()

    await interceptor.intercept_unary_unary(
        mock_method, ClientCallDetails("/some-rpc-method", 10, req_metadata, None, True), AsyncMock()
    )

    mock_method.assert_called_once()
    updated_call_details = mock_method.call_args[0][0]
    assert ("authorization", "Bearer very-secret") in updated_call_details.metadata


@pytest.mark.asyncio
async def test_rpc_method_prefix_interceptor() -> None:
    interceptor = _RpcMethodPrefixInterceptor("/public")
    mock_method = AsyncMock()

    await interceptor.intercept_unary_unary(
        mock_method,
        ClientCallDetails("/datasets.v1.DatasetService/ListDatasets", 10, None, None, True),
        AsyncMock(),
    )

    mock_method.assert_called_once()
    updated_call_details = mock_method.call_args[0][0]
    assert updated_call_details.method == "/public/datasets.v1.DatasetService/ListDatasets"
