"""
Tests for verifying path traversal protection in the query engine.
"""
# pylint: disable=import-error, redefined-outer-name
import asyncio
import tempfile
from pathlib import Path

import pytest

from doxygen_mcp.query_engine import DoxygenQueryEngine

@pytest.fixture
def traversal_env_fixture():
    """Fixture for a temporary XML directory with a traversal vulnerability."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_dir = Path(tmpdir) / "xml"
        xml_dir.mkdir()
        # Create a secret file outside the XML directory
        secret_file = Path(tmpdir) / "secret.xml"
        secret_file.write_text("<doxygen></doxygen>", encoding="utf-8")
        # Create index.xml with traversal refid
        index_xml = xml_dir / "index.xml"
        index_xml.write_text("<doxygenindex><compound refid='../secret' kind='class'><name>M</name></compound></doxygenindex>", encoding="utf-8")
        yield str(xml_dir)

def test_path_traversal_prevention(traversal_env_fixture):
    """Test that path traversal attempts via malicious refid are blocked."""
    async def run_test():
        engine = await DoxygenQueryEngine.create(traversal_env_fixture)
        result = engine.query_symbol("M")
        return result
    result = asyncio.run(run_test())
    assert "error" in result
