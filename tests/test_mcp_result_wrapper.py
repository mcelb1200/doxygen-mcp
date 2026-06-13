import asyncio
import os
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from doxygen_mcp.server import original_tool, token_crusher_tool, wrap_in_mcp_result
from doxygen_mcp.types import MCPResult


@pytest.fixture(autouse=True)
def enable_mcp_result(monkeypatch):
    monkeypatch.setenv("DOXYGEN_USE_MCP_RESULT", "true")
    monkeypatch.setenv("DOXYGEN_COMPRESS_OUTPUT", "true")
    # Reset decorator state dynamically for test context
    import doxygen_mcp.server

    monkeypatch.setattr(doxygen_mcp.server, "SHOULD_WRAP_MCP_RESULT", True)
    monkeypatch.setattr(doxygen_mcp.server, "SHOULD_COMPRESS", True)


def test_wrap_in_mcp_result_success_dict():
    res = {"namespaces": ["a", "b"]}
    wrapped = wrap_in_mcp_result(res)
    assert isinstance(wrapped, MCPResult)
    assert wrapped.success is True
    assert wrapped.data == res


def test_wrap_in_mcp_result_error_dict():
    res = {"error": "Failed to find files"}
    wrapped = wrap_in_mcp_result(res)
    assert isinstance(wrapped, MCPResult)
    assert wrapped.success is False
    assert wrapped.error == "Failed to find files"


def test_wrap_in_mcp_result_error_list():
    res = [{"error": "Another error"}]
    wrapped = wrap_in_mcp_result(res)
    assert isinstance(wrapped, MCPResult)
    assert wrapped.success is False
    assert wrapped.error == "Another error"


def test_wrap_in_mcp_result_str_success():
    res = "✅ Project created successfully"
    wrapped = wrap_in_mcp_result(res)
    assert isinstance(wrapped, MCPResult)
    assert wrapped.success is True
    assert wrapped.message == res


def test_wrap_in_mcp_result_str_error():
    res = "❌ Unexpected Doxygen version format"
    wrapped = wrap_in_mcp_result(res)
    assert isinstance(wrapped, MCPResult)
    assert wrapped.success is False
    assert wrapped.error == res


def test_wrap_in_mcp_result_str_generic():
    res = "some raw output string"
    wrapped = wrap_in_mcp_result(res)
    assert isinstance(wrapped, MCPResult)
    assert wrapped.success is True
    assert wrapped.data == res


@pytest.mark.asyncio
async def test_decorator_async_success():
    @token_crusher_tool()
    async def dummy_async_tool():
        return "✅ Success"

    res = await dummy_async_tool()
    assert isinstance(res, MCPResult)
    assert res.success is True
    assert "Success" in res.message


@pytest.mark.asyncio
async def test_decorator_async_exception():
    @token_crusher_tool()
    async def dummy_async_fail():
        raise ValueError("Fatal syntax error")

    res = await dummy_async_fail()
    assert isinstance(res, MCPResult)
    assert res.success is False
    assert "Fatal syntax err" in res.error


def test_decorator_sync_success():
    @token_crusher_tool()
    def dummy_sync_tool():
        return "✅ Success"

    res = dummy_sync_tool()
    assert isinstance(res, MCPResult)
    assert res.success is True
    assert "Success" in res.message


def test_decorator_sync_exception():
    @token_crusher_tool()
    def dummy_sync_fail():
        raise ValueError("Fatal sync error")

    res = dummy_sync_fail()
    assert isinstance(res, MCPResult)
    assert res.success is False
    assert "Fatal sync err" in res.error


def test_token_crusher_with_mcp_result():
    # Test that token crusher compresses strings inside MCPResult
    res = MCPResult(success=True, message="This is configuration and documentation")
    from doxygen_mcp.caveman import compress_payload

    compressed = compress_payload(res)
    assert isinstance(compressed, MCPResult)
    # "configuration" -> "config", "documentation" -> "docs", "and" stays
    assert "config" in compressed.message
    assert "docs" in compressed.message
