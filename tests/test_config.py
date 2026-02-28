"""
# pylint: disable=import-error, redefined-outer-name
Tests for the DoxygenConfig model.
"""
# pylint: disable=import-error, redefined-outer-name
# pylint: disable=import-error
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from doxygen_mcp.config import DoxygenConfig

class TestDoxygenConfig:
    """Test suite for DoxygenConfig."""
# pylint: disable=import-error, redefined-outer-name

    def test_from_env_basic(self):
        """Test from_env with default values and no environment variables."""
# pylint: disable=import-error, redefined-outer-name
        # Mocking utils to avoid side effects and dependency on environment
        with patch("doxygen_mcp.utils.resolve_project_path") as mock_resolve, \
             patch("doxygen_mcp.utils.get_project_name") as mock_get_name, \
             patch.dict(os.environ, {}, clear=True):

            mock_resolve.return_value = Path("/tmp/test_project")
            mock_get_name.return_value = "Test Project"

            config = DoxygenConfig.from_env()

            assert config.project_name == "Test Project"
            assert config.recursive is True  # Default value
            mock_resolve.assert_called_once()
            mock_get_name.assert_called_once_with(Path("/tmp/test_project"))

    def test_from_env_with_kwargs(self):
        """Test from_env with explicit kwargs."""
# pylint: disable=import-error, redefined-outer-name
        with patch("doxygen_mcp.utils.resolve_project_path"), \
             patch("doxygen_mcp.utils.get_project_name") as mock_get_name, \
             patch.dict(os.environ, {}, clear=True):

            config = DoxygenConfig.from_env(project_name="Custom Project", recursive=False)

            assert config.project_name == "Custom Project"
            assert config.recursive is False
            # resolve_project_path and get_project_name should not be used for project_name if provided
            mock_get_name.assert_not_called()

    def test_from_env_with_env_vars(self):
        """Test from_env with environment variable overrides."""
# pylint: disable=import-error, redefined-outer-name
        env_vars = {
            "DOXYGEN_MCP_PROJECT_NAME": "Env Project",
            "DOXYGEN_MCP_RECURSIVE": "false",
            "DOXYGEN_MCP_OUTPUT_DIRECTORY": "./env_docs",
            "DOXYGEN_MCP_OPTIMIZE_OUTPUT_FOR_C": "yes",
            "DOXYGEN_MCP_EXTRACT_PRIVATE": "1",
            "DOXYGEN_MCP_FILE_PATTERNS": "*.cpp, *.h, *.hpp"
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = DoxygenConfig.from_env()

            assert config.project_name == "Env Project"
            assert config.recursive is False
            assert config.output_directory == "./env_docs"
            assert config.optimize_output_for_c is True
            assert config.extract_private is True
            assert config.file_patterns == ["*.cpp", "*.h", "*.hpp"]
