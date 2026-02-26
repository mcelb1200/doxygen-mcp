"""
Tests for the refresh_index tool.
"""
# pylint: disable=import-error, wrong-import-position
import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from doxygen_mcp.server import refresh_index

@pytest.mark.asyncio
async def test_refresh_index_success(tmp_path):
    """Test successful index refresh."""
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "index.xml").write_text("<doxygenindex></doxygenindex>", encoding="utf-8")

    with patch("doxygen_mcp.server.resolve_project_path", return_value=tmp_path), \
         patch("doxygen_mcp.server._find_xml_dir", return_value=str(xml_dir)), \
         patch("doxygen_mcp.server.DoxygenQueryEngine") as mock_engine_cls:

        mock_engine = MagicMock()
        future = asyncio.Future()
        future.set_result(mock_engine)
        mock_engine_cls.create.return_value = future

        result = await refresh_index()
        assert "successfully" in result
        mock_engine_cls.clear_cache.assert_called_with(str(xml_dir))
        mock_engine_cls.create.assert_called_with(str(xml_dir))
