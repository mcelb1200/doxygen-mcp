"""
Tests for get_ide_environment function.
"""
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from doxygen_mcp.utils import get_ide_environment

def test_get_ide_environment_unknown():
    """Test get_ide_environment when no IDE is detected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, {}, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "unknown"
            assert context["workspace_root"] == str(temp_path)
            assert context["project_name"] == "test_project"
            assert "vscode_settings" not in context

def test_get_ide_environment_vscode_term_program():
    """Test VS Code detection via TERM_PROGRAM."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, {"TERM_PROGRAM": "vscode"}, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "vscode"

def test_get_ide_environment_vscode_ipc():
    """Test VS Code detection via VSCODE_GIT_IPC_HANDLE."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, {"VSCODE_GIT_IPC_HANDLE": "some_handle"}, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "vscode"

def test_get_ide_environment_cursor_ipc():
    """Test Cursor detection via CURSOR_GIT_IPC_HANDLE."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        env = {
            "TERM_PROGRAM": "vscode",
            "CURSOR_GIT_IPC_HANDLE": "some_handle"
        }
        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, env, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "cursor"

def test_get_ide_environment_cursor_app_path():
    """Test Cursor detection via APP_PATH."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        env = {
            "TERM_PROGRAM": "vscode",
            "APP_PATH": "/Applications/Cursor.app/Contents/MacOS/Cursor"
        }
        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, env, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "cursor"

def test_get_ide_environment_jetbrains():
    """Test JetBrains detection."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        env = {
            "TERMINAL_EMULATOR": "JetBrains-JediTerm"
        }
        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, env, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "jetbrains"

def test_get_ide_environment_vscode_settings():
    """Test loading .vscode/settings.json."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        vscode_dir = temp_path / ".vscode"
        vscode_dir.mkdir()
        settings_file = vscode_dir / "settings.json"
        settings_data = {"doxygen.path": "/usr/local/bin/doxygen"}
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings_data, f)

        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, {"TERM_PROGRAM": "vscode"}, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "vscode"
            assert context["vscode_settings"] == settings_data

def test_get_ide_environment_vscode_settings_invalid_json():
    """Test handling of invalid .vscode/settings.json."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        vscode_dir = temp_path / ".vscode"
        vscode_dir.mkdir()
        settings_file = vscode_dir / "settings.json"
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")

        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, {"TERM_PROGRAM": "vscode"}, clear=True):

            context = get_ide_environment()
            assert context["ide"] == "vscode"
            assert "vscode_settings" not in context


def test_get_ide_environment_vscode_settings_read_exception():
    """Test handling of read exception for .vscode/settings.json."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        vscode_dir = temp_path / ".vscode"
        vscode_dir.mkdir()
        settings_file = vscode_dir / "settings.json"
        # Create the file so .exists() returns True
        settings_file.touch()

        with patch("doxygen_mcp.utils.resolve_project_path", return_value=temp_path), \
             patch("doxygen_mcp.utils.get_project_name", return_value="test_project"), \
             patch.dict(os.environ, {"TERM_PROGRAM": "vscode"}, clear=True), \
             patch("builtins.open", side_effect=PermissionError("Access denied")):

            context = get_ide_environment()
            assert context["ide"] == "vscode"
            assert "vscode_settings" not in context
