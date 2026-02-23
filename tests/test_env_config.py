"""
Tests for environment-based configuration and path resolution.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from doxygen_mcp.server import (
    create_doxygen_project,
    generate_documentation,
    query_project_reference,
    _resolve_project_path
)
from doxygen_mcp.utils import resolve_project_path

@pytest.fixture
def temp_project_dir():
    """Fixture for a temporary project directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

class TestEnvConfig:
    """Test suite for environment-based configuration."""

    def test_resolve_project_path_explicit(self, temp_project_dir):
        """Test resolving path when explicitly provided"""
        resolved = resolve_project_path(temp_project_dir)
        assert resolved == Path(temp_project_dir).resolve()

    def test_resolve_project_path_env(self, temp_project_dir):
        """Test resolving path from environment variable"""
        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            resolved = resolve_project_path(None)
            assert resolved == Path(temp_project_dir).resolve()

    def test_resolve_project_path_missing(self):
        """Test fallback when path is missing entirely"""
        with patch.dict(os.environ, {}, clear=True):
            # Should resolve to CWD if nothing else found
            resolved = _resolve_project_path(None)
            assert resolved == Path.cwd()

    @pytest.mark.asyncio
    async def test_create_project_with_env(self, temp_project_dir):
        """Test creating project using environment variable for path"""
        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            result = await create_doxygen_project(
                project_name="Env Project",
                # project_path is None by default
                language="python"
            )

            assert "✅ Doxygen project 'Env Project' created successfully" in result
            assert (Path(temp_project_dir) / "Doxyfile").exists()

    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_generate_docs_with_env(self, mock_exec, temp_project_dir):
        """Test generating docs using environment variable"""
        # Create Doxyfile first
        (Path(temp_project_dir) / "Doxyfile").write_text("PROJECT_NAME=Test", encoding="utf-8")

        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            # Mock successful doxygen execution
            process = MagicMock()
            process.communicate = AsyncMock(return_value=(b"", b""))
            process.returncode = 0
            mock_exec.return_value = process

            result = await generate_documentation()

            assert "✅ Documentation generated successfully" in result

    @pytest.mark.asyncio
    async def test_query_reference_with_env_xml(self, temp_project_dir):
        """Test querying with DOXYGEN_XML_DIR"""
        xml_dir = Path(temp_project_dir) / "xml"
        xml_dir.mkdir(parents=True)
        (xml_dir / "index.xml").write_text("<doxygenindex></doxygenindex>", encoding="utf-8")

        with patch.dict(os.environ, {"DOXYGEN_XML_DIR": str(xml_dir)}):
            with patch('doxygen_mcp.server.DoxygenQueryEngine') as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.query_symbol.return_value = {
                    "kind": "class", "name": "Test", "brief": "Brief",
                    "detailed": "", "members": []
                }

                future = asyncio.Future()
                future.set_result(mock_engine)
                mock_engine_cls.create.return_value = future

                result = await query_project_reference("Test")

                assert "Documentation for class Test" in result
                mock_engine_cls.create.assert_called_with(str(xml_dir))

    @pytest.mark.asyncio
    async def test_query_reference_with_project_root_env(self, temp_project_dir):
        """Test querying with DOXYGEN_PROJECT_ROOT implying XML location"""
        # Setup standard structure: root/docs/xml
        xml_dir = Path(temp_project_dir) / "docs" / "xml"
        xml_dir.mkdir(parents=True)
        (xml_dir / "index.xml").write_text("<doxygenindex></doxygenindex>", encoding="utf-8")

        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            # Clear XML_DIR to ensure we use PROJECT_ROOT
            if "DOXYGEN_XML_DIR" in os.environ:
                del os.environ["DOXYGEN_XML_DIR"]

            with patch('doxygen_mcp.server.DoxygenQueryEngine') as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.query_symbol.return_value = {
                    "kind": "class", "name": "Test", "brief": "Brief",
                    "detailed": "", "members": []
                }

                future = asyncio.Future()
                future.set_result(mock_engine)
                mock_engine_cls.create.return_value = future

                result = await query_project_reference("Test")

                assert "Documentation for class Test" in result
                mock_engine_cls.create.assert_called_with(str(xml_dir))
