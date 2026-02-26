"""
Tests for resolve_project_path utility.
"""
# pylint: disable=import-error, redefined-outer-name
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from doxygen_mcp.utils import resolve_project_path

@pytest.fixture
def mock_cwd_fixture():
    """Fixture to mock Path.cwd()."""
    with patch("pathlib.Path.cwd") as mock:
        mock.return_value = Path("/app/project")
        yield mock

@pytest.fixture
def clean_env_fixture():
    """Fixture to clean relevant environment variables."""
    with patch.dict(os.environ, {}, clear=True):
        yield

def test_resolve_explicit_path(clean_env_fixture, mock_cwd_fixture):
    """Test resolving an explicit path."""
    # pylint: disable=unused-argument
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "1"}):
            resolved = resolve_project_path(tmpdir)
            assert resolved == Path(tmpdir).resolve()

def test_resolve_from_env(clean_env_fixture, mock_cwd_fixture):
    """Test resolving from DOXYGEN_PROJECT_ROOT."""
    # pylint: disable=unused-argument
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": tmpdir}):
            resolved = resolve_project_path(None)
            assert resolved == Path(tmpdir).resolve()
