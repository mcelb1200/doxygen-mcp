"""
Tests for Doxygen configuration model.
"""

# pylint: disable=unused-variable,import-error,wrong-import-order,unused-import

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from doxygen_mcp.config import DoxygenConfig

class TestDoxygenConfig:
    """Test the DoxygenConfig model."""
    def test_from_env_basic(self):
        """Test from_env with default values and no environment variables."""
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
        with patch("doxygen_mcp.utils.resolve_project_path") as mock_resolve, \
             patch("doxygen_mcp.utils.get_project_name") as mock_get_name, \
             patch.dict(os.environ, {}, clear=True):

            config = DoxygenConfig.from_env(project_name="Custom Project", recursive=False)

            assert config.project_name == "Custom Project"
            assert config.recursive is False
            # resolve_project_path and get_project_name should not be used for project_name if provided
            mock_get_name.assert_not_called()

    def test_from_env_with_env_vars(self):
        """Test from_env with environment variable overrides."""
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

    def test_from_env_env_overrides_kwargs(self):
        """Test that environment variables take precedence over kwargs."""
        env_vars = {
            "DOXYGEN_MCP_PROJECT_NAME": "Env Project",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = DoxygenConfig.from_env(project_name="Kwarg Project")

            assert config.project_name == "Env Project"

    def test_from_env_boolean_values(self):
        """Test various boolean environment variable values."""
        test_cases = [
            ("true", True),
            ("yes", True),
            ("1", True),
            ("false", False),
            ("no", False),
            ("0", False),
            ("anything", False),
        ]

        for env_val, expected in test_cases:
            with patch.dict(os.environ, {"DOXYGEN_MCP_RECURSIVE": env_val}, clear=True):
                config = DoxygenConfig.from_env()
                assert config.recursive is expected, f"Failed for {env_val}"

    def test_from_env_list_values(self):
        """Test list environment variable values with different spacing."""
        env_vars = {
            "DOXYGEN_MCP_INPUT_PATHS": "path1, path2 ,path3",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config = DoxygenConfig.from_env()
            assert config.input_paths == ["path1", "path2", "path3"]
