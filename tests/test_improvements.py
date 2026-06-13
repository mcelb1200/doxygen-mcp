import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from pydantic import BaseModel

from doxygen_mcp.caveman import compress_payload, compress_text
from doxygen_mcp.reporter import discover_candidates, generate_report_html
from doxygen_mcp.server import (
    generate_architecture_review,
    generate_context_report,
)


def test_caveman_text_compression():
    # Test article and filler removal
    assert compress_text("the class is a wrapper") == "class is wrapper"
    # Test synonym replacements
    assert compress_text("authentication configuration exception") == "auth config err"
    # Test whitespace cleanups
    assert compress_text("some   excessive    spaces .") == "some excessive spaces."


def test_caveman_payload_compression_dict_list():
    # Test list/dict traversal
    payload = {
        "title": "A standard configuration module",
        "values": ["the implementation", 42, True],
    }
    expected = {"title": "standard config module", "values": ["impl", 42, True]}
    assert compress_payload(payload) == expected


def test_caveman_payload_compression_tuple():
    # Test tuple traversal
    payload = ("the configuration", "a documentation file", 100)
    expected = ("config", "docs file", 100)
    assert compress_payload(payload) == expected


class DummyModel(BaseModel):
    name: str
    description: str
    count: int


def test_caveman_payload_compression_pydantic():
    # Test Pydantic BaseModel traversal
    model = DummyModel(
        name="the authentication service",
        description="really basically an implementation for databases",
        count=5,
    )
    expected_model = DummyModel(
        name="auth service", description="impl for DBs", count=5
    )
    assert compress_payload(model) == expected_model


def test_caveman_payload_compression_nested():
    # Test deeply nested payloads
    payload = {
        "level1": [
            {
                "level2_tuple": ("just a request", "the response"),
                "level2_str": "certainly a repository",
                "level2_int": 404,
            }
        ]
    }
    expected = {
        "level1": [
            {"level2_tuple": ("req", "res"), "level2_str": "repo", "level2_int": 404}
        ]
    }
    assert compress_payload(payload) == expected


def test_caveman_payload_compression_edge_cases():
    # Test edge cases: None, empty collections, empty strings
    assert compress_payload(None) is None
    assert compress_payload("") == ""
    assert compress_payload([]) == []
    assert compress_payload({}) == {}
    assert compress_payload(()) == ()
    assert compress_payload(123) == 123
    assert compress_payload(True) is True


@pytest.mark.asyncio
@patch("doxygen_mcp.server.resolve_project_path")
@patch("doxygen_mcp.server._find_xml_dir")
@patch("doxygen_mcp.server.detect_primary_language")
@patch("doxygen_mcp.server._get_git_diff")
@patch("doxygen_mcp.server.DoxygenQueryEngine.create")
async def test_generate_context_report(
    mock_engine_create, mock_git_diff, mock_lang, mock_xml_dir, mock_resolve_path
):
    mock_resolve_path.return_value = Path("/tmp/fake_project")
    mock_xml_dir.return_value = "/tmp/fake_project/docs/xml"
    mock_lang.return_value = "cpp"
    mock_git_diff.return_value = "diff --git a/file.cpp b/file.cpp"

    mock_engine = MagicMock()
    mock_engine.list_all_symbols.side_effect = lambda kind_filter: {
        "class": ["MyClass1", "MyClass2"],
        "namespace": ["MyNs"],
        "file": ["file.cpp"],
    }.get(kind_filter, [])

    mock_engine_create.return_value = mock_engine

    report = await generate_context_report("/tmp/fake_project")

    assert "Context Report" in report or "context report" in report.lower()
    assert "Structural Summary" in report or "structural summary" in report.lower()


@pytest.mark.asyncio
@patch("doxygen_mcp.server.resolve_project_path")
@patch("doxygen_mcp.server._find_xml_dir")
@patch("doxygen_mcp.server.DoxygenQueryEngine.create")
@patch("subprocess.Popen")
async def test_generate_architecture_review(
    mock_popen, mock_engine_create, mock_xml_dir, mock_resolve_path
):
    mock_resolve_path.return_value = Path("/tmp/fake_project")
    mock_xml_dir.return_value = "/tmp/fake_project/docs/xml"

    mock_engine = MagicMock()
    mock_engine.list_all_symbols.return_value = []
    mock_engine_create.return_value = mock_engine

    result = await generate_architecture_review("/tmp/fake_project")
    assert (
        "✅ Architecture review generated at" in result
        or "architecture review" in result.lower()
    )
