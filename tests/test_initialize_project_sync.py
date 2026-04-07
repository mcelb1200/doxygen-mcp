import pytest
from pathlib import Path
import tempfile
import os
import sys

# Add src and mock_modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mock_modules"))

from doxygen_mcp.server import _initialize_project_sync
from doxygen_mcp.config import DoxygenConfig

def test_initialize_project_sync_success():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test_project"
        config = DoxygenConfig(project_name="Test")

        result = _initialize_project_sync(project_path, config)

        assert result is None
        assert project_path.is_dir()
        assert (project_path / "Doxyfile").exists()

        with open(project_path / "Doxyfile", "r") as f:
            content = f.read()
            assert 'PROJECT_NAME           = "Test"' in content

def test_initialize_project_sync_not_a_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / "not_a_dir"
        file_path.touch()

        config = DoxygenConfig()
        result = _initialize_project_sync(file_path, config)

        assert "❌ Path exists but is not a directory" in result

def test_initialize_project_sync_already_exists():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        doxyfile = project_path / "Doxyfile"
        doxyfile.touch()

        config = DoxygenConfig()
        result = _initialize_project_sync(project_path, config)

        assert "❌ Doxyfile already exists" in result

def test_initialize_project_sync_symlink_security():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        doxyfile = project_path / "Doxyfile"
        # Create a symlink
        target = project_path / "target"
        target.touch()
        os.symlink(target, doxyfile)

        config = DoxygenConfig()
        result = _initialize_project_sync(project_path, config)

        assert "❌ Security Error" in result
        assert "is a symlink" in result
