import os
import sys
import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from doxygen_mcp.reporter import (
    discover_candidates,
    get_git_version,
    generate_report_html,
)


def test_discover_candidates_tight_coupling():
    engine = MagicMock()
    engine.list_all_symbols.return_value = ["ClassA", "ClassB"]

    def mock_get_symbol_connections(cls):
        if cls == "ClassA":
            return {"members": [{"references": ["ClassB"]}]}
        elif cls == "ClassB":
            return {"members": [{"references": ["ClassA"]}]}
        return {}

    engine.get_symbol_connections = mock_get_symbol_connections
    engine.query_symbol.return_value = {"location": {"file": "file.cpp"}}

    candidates = discover_candidates(engine, Path("/fake"))
    assert len(candidates) == 1
    assert "Consolidate Coupled Classes" in candidates[0]["title"]
    assert "ClassA" in candidates[0]["title"]
    assert "ClassB" in candidates[0]["title"]
    assert candidates[0]["badge_strength"] == "Strong"


def test_discover_candidates_deep_inheritance():
    engine = MagicMock()
    engine.list_all_symbols.return_value = ["ClassC"]

    def mock_get_symbol_connections(cls):
        if cls == "ClassC":
            return {
                "base_classes": ["BaseC"],
                "derived_classes": ["DerivedC"],
            }
        return {}

    engine.get_symbol_connections = mock_get_symbol_connections
    engine.query_symbol.return_value = {"location": {"file": "file.cpp"}}

    candidates = discover_candidates(engine, Path("/fake"))
    assert len(candidates) == 1
    assert "Flatten Deep Inheritance of ClassC" in candidates[0]["title"]
    assert candidates[0]["badge_strength"] == "Worth exploring"


def test_discover_candidates_fallback():
    engine = MagicMock()
    engine.list_all_symbols.return_value = []

    candidates = discover_candidates(engine, Path("/fake"))
    assert len(candidates) == 1
    assert candidates[0]["title"] == "Consolidate Doxygen MCP Config and Server Utilities"
    assert candidates[0]["badge_strength"] == "Worth exploring"


@patch("subprocess.run")
def test_get_git_version_success(mock_run):
    mock_run.return_value = MagicMock(stdout="abcdef1234567890\n")
    version = get_git_version(Path("/fake"))
    assert version == "abcdef1234567890"


@patch("subprocess.run")
def test_get_git_version_doxyfile_fallback(mock_run, tmp_path):
    mock_run.side_effect = Exception("Git failed")

    # Create a dummy Doxyfile
    doxyfile = tmp_path / "Doxyfile"
    doxyfile.write_text("PROJECT_NAME=Test")

    version = get_git_version(tmp_path)
    # The sha256 of "PROJECT_NAME=Test" is 87cf2011f1acf3be...
    # first 16 chars: 87cf2011f1acf3be
    assert version == "87cf2011f1acf3be"


@patch("subprocess.run")
def test_get_git_version_no_vcs(mock_run, tmp_path):
    mock_run.side_effect = Exception("Git failed")

    # Ensure no Doxyfile exists
    version = get_git_version(tmp_path)
    assert version == "no-vcs-version"


@pytest.mark.asyncio
@patch("doxygen_mcp.reporter.discover_candidates")
@patch("doxygen_mcp.reporter.get_git_version")
@patch.dict("doxygen_mcp.query_engine.DoxygenQueryEngine._cache", {"/fake/xml": MagicMock()})
async def test_generate_report_html_cache_hit(mock_git_version, mock_discover):
    # Set the cache value manually so that `.get()` will find it
    from doxygen_mcp.query_engine import DoxygenQueryEngine
    mock_engine = MagicMock()
    DoxygenQueryEngine._cache[str(Path("/fake/xml").absolute())] = mock_engine

    mock_git_version.return_value = "v1.0"
    mock_discover.return_value = [{
        "title": "Mock Candidate",
        "badge_strength": "Strong",
        "badge_category": "mock-cat",
        "files": ["file1.cpp"],
        "mermaid_before": "A-->B",
        "mermaid_after": "B-->A",
        "problem": "Problem X",
        "solution": "Solution Y",
        "wins": ["Win Z"]
    }]

    html = generate_report_html(Path("/fake"), "/fake/xml")

    assert "<!doctype html>" in html
    assert "<title>Architecture review — fake</title>" in html
    assert "Mock Candidate" in html
    assert "v1.0" in html


# Since asyncio.run is called in the target function, this test should be synchronous.
@patch("doxygen_mcp.reporter.discover_candidates")
@patch("doxygen_mcp.reporter.get_git_version")
@patch("asyncio.run")
def test_generate_report_html_cache_miss(mock_asyncio_run, mock_git_version, mock_discover):
    # Ensure cache is empty
    from doxygen_mcp.query_engine import DoxygenQueryEngine
    DoxygenQueryEngine._cache.clear()

    mock_engine = MagicMock()
    mock_asyncio_run.return_value = mock_engine

    mock_git_version.return_value = "v2.0"
    mock_discover.return_value = [{
        "title": "Fallback Candidate",
        "badge_strength": "Speculative",
        "badge_category": "mock-cat",
        "files": ["file2.cpp"],
        "mermaid_before": "A-->B",
        "mermaid_after": "B-->A",
        "problem": "Problem X",
        "solution": "Solution Y",
        "wins": ["Win Z"]
    }]

    # Mocking create is not strictly necessary if we patch asyncio.run directly,
    # but we can patch create to prevent real objects from being passed to asyncio.run
    with patch("doxygen_mcp.query_engine.DoxygenQueryEngine.create", new_callable=MagicMock) as mock_create:
        mock_create.return_value = "dummy_coro"
        html = generate_report_html(Path("/fake"), "/fake/xml")
        mock_create.assert_called_once_with("/fake/xml")
        mock_asyncio_run.assert_called_once_with("dummy_coro")

    assert "<!doctype html>" in html
    assert "Fallback Candidate" in html
    assert "v2.0" in html
