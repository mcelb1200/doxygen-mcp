"""
Tests for get_active_context function.
"""
# pylint: disable=import-error
import os
from unittest.mock import patch

from doxygen_mcp.utils import get_active_context

def test_get_active_context_all_set():
    """Test get_active_context when all environment variables are set."""
    env_vars = {
        "MCP_ACTIVE_FILE": "src/main.py",
        "MCP_CURSOR_LINE": "42",
        "MCP_CURSOR_COLUMN": "10",
        "MCP_SELECTED_TEXT": "print('hello')"
    }
    with patch.dict(os.environ, env_vars, clear=True):
        result = get_active_context()
        assert result == {
            "active_file": "src/main.py",
            "cursor_line": "42",
            "cursor_column": "10",
            "selected_text": "print('hello')"
        }

def test_get_active_context_none_set():
    """Test get_active_context when no environment variables are set."""
    with patch.dict(os.environ, {}, clear=True):
        result = get_active_context()
        assert result == {
            "active_file": None,
            "cursor_line": None,
            "cursor_column": None,
            "selected_text": None
        }

def test_get_active_context_partially_set():
    """Test get_active_context when only some environment variables are set."""
    env_vars = {
        "MCP_ACTIVE_FILE": "src/utils.py",
        "MCP_CURSOR_LINE": "100"
    }
    with patch.dict(os.environ, env_vars, clear=True):
        result = get_active_context()
        assert result == {
            "active_file": "src/utils.py",
            "cursor_line": "100",
            "cursor_column": None,
            "selected_text": None
        }
