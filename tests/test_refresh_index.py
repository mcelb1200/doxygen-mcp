"""
Tests for the refresh_index tool in doxygen_mcp.server.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from doxygen_mcp.server import refresh_index

@pytest.mark.asyncio
async def test_refresh_index_success():
    """Test successful index refresh."""
    mock_path = Path("/mock/project")
    mock_xml_dir = "/mock/project/xml"

    with patch('doxygen_mcp.server.resolve_project_path', return_value=mock_path) as mock_resolve, \
         patch('doxygen_mcp.server._find_xml_dir', return_value=mock_xml_dir) as mock_find_xml, \
         patch('doxygen_mcp.server.DoxygenQueryEngine') as mock_engine:

        # Setup async create method
        mock_engine.create = AsyncMock()

        result = await refresh_index(project_path="/mock/project")

        assert "✅ Doxygen index refreshed successfully." in result

        mock_resolve.assert_called_with("/mock/project")
        mock_find_xml.assert_called_with(mock_path)
        mock_engine.clear_cache.assert_called_once_with(mock_xml_dir)
        mock_engine.create.assert_awaited_once_with(mock_xml_dir)

@pytest.mark.asyncio
async def test_refresh_index_no_xml():
    """Test refresh index when XML directory is not found."""
    mock_path = Path("/mock/project")

    with patch('doxygen_mcp.server.resolve_project_path', return_value=mock_path) as mock_resolve, \
         patch('doxygen_mcp.server._find_xml_dir', return_value=None) as mock_find_xml, \
         patch('doxygen_mcp.server.DoxygenQueryEngine') as mock_engine:

        result = await refresh_index(project_path="/mock/project")

        assert "❌ Doxygen XML not found. Generate documentation first." in result

        mock_resolve.assert_called_with("/mock/project")
        mock_find_xml.assert_called_with(mock_path)
        mock_engine.clear_cache.assert_not_called()
        mock_engine.create.assert_not_called()

@pytest.mark.asyncio
async def test_refresh_index_exception():
    """Test refresh index when an exception occurs."""
    error_msg = "Test Error"

    with patch('doxygen_mcp.server.resolve_project_path', side_effect=Exception(error_msg)):
        result = await refresh_index(project_path="/mock/project")

        assert f"❌ Error refreshing index: {error_msg}" in result
