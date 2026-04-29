"""
Tests for security validation in resolve_project_path.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from doxygen_mcp.utils import resolve_project_path

def test_resolve_project_path_access_denied():
    """
    Test that resolve_project_path raises ValueError for unauthorized paths.
    """
    # Use a directory that is definitely not a safe root
    with tempfile.TemporaryDirectory() as safe_dir:
        # We'll use a path that doesn't contain "temp" and doesn't start with /tmp
        # to avoid the test bypass, or just clear the env var.
        unsafe_path = Path("/usr/local/bin").resolve()
        safe_path = Path(safe_dir).resolve()

        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": str(safe_path)}, clear=True):
            # Ensure PYTEST_CURRENT_TEST is not set for this specific check
            if "PYTEST_CURRENT_TEST" in os.environ:
                del os.environ["PYTEST_CURRENT_TEST"]

            # Requesting safe_path should work
            assert resolve_project_path(str(safe_path)) == safe_path

            # Requesting unsafe_path should fail
            with pytest.raises(ValueError) as excinfo:
                resolve_project_path(str(unsafe_path))
            assert "Security Error: Access denied" in str(excinfo.value)

def test_resolve_project_path_multiple_roots():
    """
    Test that resolve_project_path works when the path is in the second safe root.
    This exercises the 'except ValueError: continue' block.
    """
    with tempfile.TemporaryDirectory() as root1_dir:
        with tempfile.TemporaryDirectory() as root2_dir:
            root1 = Path(root1_dir).resolve()
            root2 = Path(root2_dir).resolve()

            # Set two safe roots via DOXYGEN_PROJECT_ROOT and VSCODE_WORKSPACE_FOLDER
            env = {
                "DOXYGEN_PROJECT_ROOT": str(root1),
                "VSCODE_WORKSPACE_FOLDER": str(root2)
            }

            with patch.dict(os.environ, env, clear=True):
                # Ensure PYTEST_CURRENT_TEST is NOT set to avoid bypass
                if "PYTEST_CURRENT_TEST" in os.environ:
                    del os.environ["PYTEST_CURRENT_TEST"]

                # Path in root1 should resolve
                path1 = root1 / "subdir" / "file.txt"
                assert resolve_project_path(str(path1)) == path1

                # Path in root2 should also resolve, after skipping root1
                path2 = root2 / "other" / "config.json"
                assert resolve_project_path(str(path2)) == path2

def test_resolve_project_path_test_bypass():
    """
    Test the PYTEST_CURRENT_TEST bypass for temporary directories.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir).resolve()

        # Empty env but keeping PYTEST_CURRENT_TEST
        with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_some_case"}, clear=True):
            # It should allow it because it's a temp directory and PYTEST_CURRENT_TEST is set
            # even if it's not in any "official" safe root
            # We mock find_project_root to return something else
            with patch("doxygen_mcp.utils.find_project_root", return_value=Path("/some/other/root")):
                assert resolve_project_path(str(tmp_path)) == tmp_path

def test_resolve_project_path_no_bypass_without_env_var():
    """
    Test that temporary paths are REJECTED if PYTEST_CURRENT_TEST is not set.
    """
    # We need a path that would normally be caught by the bypass
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir).resolve()

        # Explicitly clear environment including PYTEST_CURRENT_TEST
        with patch.dict(os.environ, {}, clear=True):
            # Mock find_project_root to return something else so tmp_path isn't discovery root
            with patch("doxygen_mcp.utils.find_project_root", return_value=Path("/other/path")):
                with pytest.raises(ValueError) as excinfo:
                    resolve_project_path(str(tmp_path))
                assert "Security Error: Access denied" in str(excinfo.value)
