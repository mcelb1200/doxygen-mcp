"""
Tests for doxy_context tool.
"""

# pylint: disable=import-error
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest  # pylint: disable=import-error

from doxygen_mcp.server import doxy_context  # pylint: disable=import-error


@pytest.mark.asyncio
async def test_doxy_context_success():
    """Test doxy_context when a Doxyfile exists"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        doxyfile_path = temp_path / "Doxyfile"
        doxyfile_path.write_text("PROJECT_NAME = TestProject", encoding="utf-8")

        # Mock dependencies in server.py
        ide_env = {
            "ide": "vscode",
            "workspace_root": str(temp_path),
            "project_name": "TestProject",
        }
        active_ctx = {
            "active_file": "main.py",
            "cursor_line": "10",
            "cursor_column": "1",
            "selected_text": None,
        }

        with (
            patch("doxygen_mcp.server.resolve_project_path", return_value=temp_path),
            patch("doxygen_mcp.server.detect_primary_language", return_value="python"),
            patch("doxygen_mcp.server.get_ide_environment", return_value=ide_env),
            patch("doxygen_mcp.server.get_active_context", return_value=active_ctx),
        ):

            result = await doxy_context()

            assert result["project_root"] == str(temp_path)
            assert result["detected_language"] == "python"
            assert result["ide_environment"]["ide"] == "vscode"
            assert result["active_context"]["active_file"] == "main.py"
            assert result["doxygen_status"]["has_doxyfile"] is True
            assert result["doxygen_status"]["config_path"] == str(doxyfile_path)


@pytest.mark.asyncio
async def test_doxy_context_no_doxyfile():
    """Test doxy_context when no Doxyfile exists"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Mock dependencies in server.py
        ide_env = {"ide": "unknown", "workspace_root": str(temp_path)}
        with (
            patch("doxygen_mcp.server.resolve_project_path", return_value=temp_path),
            patch("doxygen_mcp.server.detect_primary_language", return_value="mixed"),
            patch("doxygen_mcp.server.get_ide_environment", return_value=ide_env),
            patch("doxygen_mcp.server.get_active_context", return_value={}),
        ):

            result = await doxy_context()

            assert result["project_root"] == str(temp_path)
            assert result["doxygen_status"]["has_doxyfile"] is False
            assert result["doxygen_status"]["config_path"] is None


@pytest.mark.asyncio
async def test_doxy_context_exception():
    """Test doxy_context when an exception occurs"""
    with patch(
        "doxygen_mcp.server.resolve_project_path", side_effect=Exception("Test Error")
    ):
        result = await doxy_context()

        assert result == {"error": "Test Error"}
