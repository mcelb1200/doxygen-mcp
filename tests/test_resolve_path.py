
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from doxygen_mcp.utils import resolve_project_path, find_project_root

@pytest.fixture
def mock_cwd(monkeypatch):
    """Mock Path.cwd() and os.getcwd() to return a predictable path."""
    mock_path = Path("/mock/cwd")

    # Patch os.getcwd
    monkeypatch.setattr(os, "getcwd", lambda: str(mock_path))

    # Patch Path.cwd just in case
    with patch("pathlib.Path.cwd") as mock:
        mock.return_value = mock_path
        yield mock

@pytest.fixture
def clean_env(monkeypatch):
    """Yield a clean environment without DOXYGEN_ variables."""
    # Use monkeypatch to remove variables
    for key in list(os.environ.keys()):
        if key.startswith("DOXYGEN_") or key in ["VSCODE_WORKSPACE_FOLDER", "CURSOR_WORKSPACE_PATH", "GEMINI_PROJECT_ROOT", "ACTIVE_WORKSPACE_PATH", "PWD"]:
            monkeypatch.delenv(key, raising=False)

    # Remove PYTEST_CURRENT_TEST to ensure strict mode in tests
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

def mock_path_func(path, *args, **kwargs):
    """Helper for mocking os.path functions that accept kwargs like strict."""
    return str(path)

def test_resolve_no_args_defaults_to_discovery(clean_env, mock_cwd):
    """Test resolution defaults to discovery (cwd) when no env vars set."""
    # Mock find_project_root to return cwd
    with patch("doxygen_mcp.utils.find_project_root") as mock_find:
        mock_find.return_value = Path("/mock/cwd")

        result = resolve_project_path()
        assert result == Path("/mock/cwd")

def test_resolve_doxygen_project_root_priority(clean_env):
    """Test DOXYGEN_PROJECT_ROOT environment variable takes priority."""
    expected_root = Path("/mock/env/root")

    with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": str(expected_root)}):
        with patch("os.path.abspath", side_effect=mock_path_func):
            with patch("os.path.realpath", side_effect=mock_path_func):
                result = resolve_project_path()
                assert result == expected_root

def test_resolve_ide_workspace_priority(clean_env, mock_cwd):
    """Test IDE workspace variables take priority over discovery."""
    ide_root = Path("/mock/ide/root")

    with patch.dict(os.environ, {"VSCODE_WORKSPACE_FOLDER": str(ide_root)}):
        # IDE path must be a directory
        with patch("os.path.isdir", return_value=True):
            with patch("os.path.abspath", side_effect=mock_path_func):
                with patch("os.path.realpath", side_effect=mock_path_func):
                    result = resolve_project_path()
                    assert result == ide_root

def test_resolve_explicit_path_safe(clean_env):
    """Test explicit path argument is accepted if within safe roots (discovered)."""
    root = Path("/mock/root")
    subpath = root / "subdir"

    with patch("doxygen_mcp.utils.find_project_root", return_value=root):
        with patch("os.path.abspath", side_effect=mock_path_func):
            with patch("os.path.realpath", side_effect=mock_path_func):
                result = resolve_project_path(str(subpath))
                assert result == subpath

def test_resolve_explicit_path_unsafe(clean_env):
    """Test explicit path argument is rejected if outside safe roots."""
    root = Path("/mock/root")
    unsafe_path = Path("/unsafe/path")

    with patch("doxygen_mcp.utils.find_project_root", return_value=root):
        with patch("os.path.abspath", side_effect=mock_path_func):
            with patch("os.path.realpath", side_effect=mock_path_func):
                with pytest.raises(ValueError, match="Security Error"):
                    resolve_project_path(str(unsafe_path))

def test_resolve_explicit_path_traversal(clean_env):
    """Test explicit path argument attempting traversal is rejected."""
    root = Path("/mock/root")
    traversal_path = "/mock/root/../secret"

    with patch("doxygen_mcp.utils.find_project_root", return_value=root):
        def simple_realpath(path, *args, **kwargs):
            return os.path.normpath(path)

        with patch("os.path.abspath", side_effect=simple_realpath):
            with patch("os.path.realpath", side_effect=simple_realpath):
                with pytest.raises(ValueError, match="Security Error"):
                    resolve_project_path(traversal_path)

def test_allowed_paths_env(clean_env):
    """Test DOXYGEN_ALLOWED_PATHS adds to safe roots."""
    allowed = Path("/mock/allowed")
    target = allowed / "file.txt"

    # Use patch.dict instead of monkeypatch context for single setting
    with patch.dict(os.environ, {"DOXYGEN_ALLOWED_PATHS": str(allowed)}):
        with patch("doxygen_mcp.utils.find_project_root", return_value=Path("/mock/other")):
            with patch("os.path.abspath", side_effect=mock_path_func):
                with patch("os.path.realpath", side_effect=mock_path_func):
                    result = resolve_project_path(str(target))
                    assert result == target

def test_pytest_bypass(monkeypatch):
    """Test PYTEST_CURRENT_TEST allows /tmp paths."""
    # Ensure PYTEST_CURRENT_TEST is set
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_pytest_bypass")

    tmp_path = Path("/tmp/doxygen_test_123")

    with patch("os.path.abspath", side_effect=mock_path_func):
        with patch("os.path.realpath", side_effect=mock_path_func):
            with patch("doxygen_mcp.utils.find_project_root", return_value=Path("/mock/cwd")):
                result = resolve_project_path(str(tmp_path))
                assert result == tmp_path

def test_symlink_resolution_security(monkeypatch):
    """
    Test that symlinks are resolved to their real paths before security checks.
    """
    # Explicitly remove PYTEST_CURRENT_TEST using monkeypatch
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir).resolve()

        safe_root = base / "safe_root"
        safe_root.mkdir()

        secret_dir = base / "secret"
        secret_dir.mkdir()

        link_path = safe_root / "link_to_secret"
        try:
            os.symlink(secret_dir, link_path)
        except OSError:
            pytest.skip("Symlinks not supported")

        # Mock find_project_root to return safe_root
        with patch("doxygen_mcp.utils.find_project_root", return_value=safe_root):
             # Also ensure we don't pick up PWD which might be /app
             monkeypatch.delenv("PWD", raising=False)

             try:
                 resolve_project_path(str(link_path))
             except ValueError as e:
                 assert "Security Error" in str(e)
                 return

             pytest.fail("Did not raise Security Error for symlink traversal")
