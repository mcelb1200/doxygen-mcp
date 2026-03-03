"""
Tests for get_project_name function.
"""
# pylint: disable=import-error
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from doxygen_mcp.utils import get_project_name

def test_get_project_name_from_doxygen_project_name_env():
    """Test extracting project name from DOXYGEN_PROJECT_NAME env var."""
    resolved_path = Path("/tmp/my_project_path")
    with patch.dict(os.environ, {"DOXYGEN_PROJECT_NAME": "My Custom Project"}):
        assert get_project_name(resolved_path) == "My Custom Project"

def test_get_project_name_from_ide_vars():
    """Test extracting project name from IDE specific variables."""
    resolved_path = Path("/tmp/my_project_path")

    # Test VSCODE_WORKSPACE_NAME
    with patch.dict(os.environ, {"VSCODE_WORKSPACE_NAME": "VSCode Project"}, clear=True):
        assert get_project_name(resolved_path) == "VSCode Project"

    # Test CURSOR_PROJECT_NAME
    with patch.dict(os.environ, {"CURSOR_PROJECT_NAME": "Cursor Project"}, clear=True):
        assert get_project_name(resolved_path) == "Cursor Project"

    # Test PROJECT_NAME
    with patch.dict(os.environ, {"PROJECT_NAME": "Generic Project"}, clear=True):
        assert get_project_name(resolved_path) == "Generic Project"

def test_get_project_name_from_resolved_path():
    """Test extracting project name from resolved path when no env vars are set."""
    resolved_path = Path("/tmp/my_project_path")
    with patch.dict(os.environ, {}, clear=True):
        assert get_project_name(resolved_path) == "my_project_path"

def test_get_project_name_priority():
    """Test the priority of project name resolution."""
    resolved_path = Path("/tmp/my_project_path")

    env_vars = {
        "DOXYGEN_PROJECT_NAME": "Priority 1",
        "VSCODE_WORKSPACE_NAME": "Priority 2",
        "CURSOR_PROJECT_NAME": "Priority 3",
        "PROJECT_NAME": "Priority 4",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        assert get_project_name(resolved_path) == "Priority 1"

    env_vars.pop("DOXYGEN_PROJECT_NAME")
    with patch.dict(os.environ, env_vars, clear=True):
        assert get_project_name(resolved_path) == "Priority 2"

    env_vars.pop("VSCODE_WORKSPACE_NAME")
    with patch.dict(os.environ, env_vars, clear=True):
        assert get_project_name(resolved_path) == "Priority 3"

    env_vars.pop("CURSOR_PROJECT_NAME")
    with patch.dict(os.environ, env_vars, clear=True):
        assert get_project_name(resolved_path) == "Priority 4"
