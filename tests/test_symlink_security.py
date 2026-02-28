"""
Tests for verifying symlink traversal protection.
"""
# pylint: disable=import-error, redefined-outer-name, duplicate-code
import os
from pathlib import Path
from unittest.mock import patch

from doxygen_mcp.config import DoxygenConfig

class TestSymlinkSecurity:
    """Test suite for symlink security configuration."""

    def test_exclude_symlinks_default_true(self):
        """Test that exclude_symlinks defaults to True."""
        config = DoxygenConfig(project_name="Test Project")
        assert config.exclude_symlinks is True

    def test_doxyfile_generation_includes_exclude_symlinks(self):
        """Test that to_doxyfile includes EXCLUDE_SYMLINKS = YES by default."""
        config = DoxygenConfig(project_name="Test Project")
        doxyfile_content = config.to_doxyfile()
        assert "EXCLUDE_SYMLINKS       = YES" in doxyfile_content

    def test_doxyfile_generation_exclude_symlinks_false(self):
        """Test that to_doxyfile includes EXCLUDE_SYMLINKS = NO when explicitly disabled."""
        config = DoxygenConfig(project_name="Test Project", exclude_symlinks=False)
        doxyfile_content = config.to_doxyfile()
        assert "EXCLUDE_SYMLINKS       = NO" in doxyfile_content

    def test_env_var_override_exclude_symlinks(self):
        """Test that environment variable overrides exclude_symlinks."""
        with patch.dict(os.environ, {"DOXYGEN_MCP_EXCLUDE_SYMLINKS": "false"}, clear=True):
            with patch("doxygen_mcp.utils.resolve_project_path") as mock_resolve, \
                 patch("doxygen_mcp.utils.get_project_name") as mock_get_name:

                mock_resolve.return_value = Path("/tmp/test_project")
                mock_get_name.return_value = "Test Project"

                config = DoxygenConfig.from_env()
                assert config.exclude_symlinks is False
