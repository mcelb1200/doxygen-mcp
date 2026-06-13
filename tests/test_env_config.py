"""
Tests for environment-based configuration and path resolution.
"""

# pylint: disable=import-error, redefined-outer-name
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # pylint: disable=import-error

# pylint: disable=import-error
from doxygen_mcp.server import doxy_create, doxy_generate, doxy_query
from doxygen_mcp.utils import resolve_project_path

# pylint: enable=import-error

# Add src to path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)


@pytest.fixture
def temp_project_dir():
    """Fixture for a temporary project directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


# pylint: disable=redefined-outer-name
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
            resolved = resolve_project_path(None)
            assert resolved == Path.cwd()

    @pytest.mark.asyncio
    async def test_create_project_with_env(self, temp_project_dir):
        """Test creating project using environment variable for path"""
        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            result = await doxy_create(
                project_name="Env Project",
                # project_path is None by default
                language="python",
            )

            assert "✅ Doxygen project 'Env Project' created successfully" in result
            assert (Path(temp_project_dir) / "Doxyfile").exists()

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_generate_docs_with_env(self, mock_exec, temp_project_dir):
        """Test generating docs using environment variable"""
        # Create Doxyfile first
        (Path(temp_project_dir) / "Doxyfile").write_text(
            "PROJECT_NAME=Test", encoding="utf-8"
        )

        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            with patch(
                "asyncio.create_subprocess_exec", new_callable=AsyncMock
            ) as mock_exec:
                process = MagicMock()
                process.communicate = AsyncMock(return_value=(b"", b""))
                process.returncode = 0
                mock_exec.return_value = process

                with patch(
                    "doxygen_mcp.server.get_doxygen_executable",
                    return_value="/usr/bin/doxygen",
                ):
                    result = await doxy_generate(
                        # project_path is None
                    )

                assert "✅ Documentation generated successfully" in result

    @pytest.mark.asyncio
    async def test_query_reference_with_env_xml(self, temp_project_dir):
        """Test querying with DOXYGEN_XML_DIR"""
        xml_dir = Path(temp_project_dir) / "xml"
        xml_dir.mkdir(parents=True)
        (xml_dir / "index.xml").write_text(
            "<doxygenindex></doxygenindex>", encoding="utf-8"
        )

        with patch.dict(os.environ, {"DOXYGEN_XML_DIR": str(xml_dir)}):
            with patch("doxygen_mcp.server.DoxygenQueryEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.query_symbol.return_value = {
                    "kind": "class",
                    "name": "Test",
                    "brief": "Brief",
                    "detailed": "",
                    "members": [],
                }

                future = asyncio.Future()
                future.set_result(mock_engine)
                mock_engine_cls.create.return_value = future

                result = await doxy_query("Test")

                assert "Documentation for class Test" in result
                mock_engine_cls.create.assert_called_with(str(xml_dir))

    @pytest.mark.asyncio
    async def test_query_reference_with_project_root_env(self, temp_project_dir):
        """Test querying with DOXYGEN_PROJECT_ROOT implying XML location"""
        # Setup standard structure: root/docs/xml
        xml_dir = Path(temp_project_dir) / "docs" / "xml"
        xml_dir.mkdir(parents=True)
        (xml_dir / "index.xml").write_text(
            "<doxygenindex></doxygenindex>", encoding="utf-8"
        )

        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            # Clear XML_DIR to ensure we use PROJECT_ROOT
            if "DOXYGEN_XML_DIR" in os.environ:
                del os.environ["DOXYGEN_XML_DIR"]

            with patch("doxygen_mcp.server.DoxygenQueryEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.query_symbol.return_value = {
                    "kind": "class",
                    "name": "Test",
                    "brief": "Brief",
                    "detailed": "",
                    "members": [],
                }

                future = asyncio.Future()
                future.set_result(mock_engine)
                mock_engine_cls.create.return_value = future

                result = await doxy_query("Test")

                assert "Documentation for class Test" in result
                mock_engine_cls.create.assert_called_with(str(xml_dir))

    @pytest.mark.asyncio
    async def test_query_reference_with_project_json_xml(self, temp_project_dir):
        """Test querying with xml_dir in doxygen_mcp.json"""
        import json

        xml_dir = Path(temp_project_dir) / "custom_xml_dir"
        xml_dir.mkdir(parents=True)
        (xml_dir / "index.xml").write_text(
            "<doxygenindex></doxygenindex>", encoding="utf-8"
        )

        config_file = Path(temp_project_dir) / "doxygen_mcp.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump({"xml_dir": "custom_xml_dir"}, f)

        with patch.dict(os.environ, {"DOXYGEN_PROJECT_ROOT": temp_project_dir}):
            # Clear DOXYGEN_XML_DIR to force using doxygen_mcp.json
            if "DOXYGEN_XML_DIR" in os.environ:
                del os.environ["DOXYGEN_XML_DIR"]

            with patch("doxygen_mcp.server.DoxygenQueryEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.query_symbol.return_value = {
                    "kind": "class",
                    "name": "Test",
                    "brief": "Brief",
                    "detailed": "",
                    "members": [],
                }

                future = asyncio.Future()
                future.set_result(mock_engine)
                mock_engine_cls.create.return_value = future

                result = await doxy_query("Test")

                assert "Documentation for class Test" in result
                mock_engine_cls.create.assert_called_with(str(xml_dir.resolve()))

    def test_resolve_project_path_expansion(self):
        """Test resolving path with home-relative ~ and environment variables"""
        home_path = Path.home().resolve()
        with patch.dict(
            os.environ,
            {"DOXYGEN_PROJECT_ROOT": "~/test_project_dir", "TEST_VAR": "foo"},
        ):
            resolved = resolve_project_path(None)
            assert resolved == (home_path / "test_project_dir").resolve()

        with patch.dict(
            os.environ, {"DOXYGEN_PROJECT_ROOT": "~/test_$TEST_VAR", "TEST_VAR": "foo"}
        ):
            resolved = resolve_project_path(None)
            assert resolved == (home_path / "test_foo").resolve()

    def test_find_project_root_in_current_dir(self, tmp_path):
        """Test when the marker is in the starting directory."""
        marker_file = tmp_path / ".git"
        marker_file.mkdir()

        from doxygen_mcp.utils import find_project_root

        result = find_project_root(tmp_path)
        assert result == tmp_path.resolve()

    def test_find_project_root_in_parent_dir(self, tmp_path):
        """Test when the marker is in a parent directory."""
        from doxygen_mcp.utils import find_project_root

        marker_file = tmp_path / "pyproject.toml"
        marker_file.touch()

        sub_dir = tmp_path / "src" / "module"
        sub_dir.mkdir(parents=True)

        result = find_project_root(sub_dir)
        assert result == tmp_path.resolve()

    def test_find_project_root_in_grandparent_dir(self, tmp_path):
        """Test when the marker is in a grandparent directory."""
        from doxygen_mcp.utils import find_project_root

        marker_dir = tmp_path / ".svn"
        marker_dir.mkdir()

        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)

        result = find_project_root(deep_dir, markers=[".svn"])
        assert result == tmp_path.resolve()

    def test_find_project_root_not_found(self, tmp_path):
        """Test when no marker is found in the entire hierarchy."""
        from doxygen_mcp.utils import find_project_root

        # Create a deep structure with no markers
        deep_dir = tmp_path / "x" / "y" / "z"
        deep_dir.mkdir(parents=True)

        with pytest.raises(
            FileNotFoundError, match="Could not find project root containing any of"
        ):
            find_project_root(deep_dir)

    def test_find_project_root_custom_markers(self, tmp_path):
        """Test using custom markers."""
        from doxygen_mcp.utils import find_project_root

        default_marker = tmp_path / ".git"
        default_marker.mkdir()

        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()

        custom_marker = sub_dir / "custom_marker.txt"
        custom_marker.touch()

        deep_dir = sub_dir / "deep"
        deep_dir.mkdir()

        # With default markers, it would find .git in tmp_path
        # But with custom markers, it should find custom_marker.txt in sub_dir
        result = find_project_root(deep_dir, markers=["custom_marker.txt"])
        assert result == sub_dir.resolve()

    def test_find_project_root_custom_markers_not_found(self, tmp_path):
        """Test custom markers when not found."""
        from doxygen_mcp.utils import find_project_root

        default_marker = tmp_path / ".git"
        default_marker.mkdir()

        deep_dir = tmp_path / "subdir" / "deep"
        deep_dir.mkdir(parents=True)

        with pytest.raises(
            FileNotFoundError, match="Could not find project root containing any of"
        ):
            find_project_root(deep_dir, markers=["non_existent_marker.txt"])
