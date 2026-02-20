import pytest
import tempfile
import os
import asyncio
from pathlib import Path
from doxygen_mcp.query_engine import DoxygenQueryEngine

@pytest.fixture
def traversal_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_dir = Path(tmpdir) / "xml"
        xml_dir.mkdir()

        # Create a secret file outside the XML directory
        secret_file = Path(tmpdir) / "secret.xml"
        secret_file.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="secret" kind="class">
    <compoundname>SECRET_DATA</compoundname>
    <briefdescription><para>You found me!</para></briefdescription>
  </compounddef>
</doxygen>
""")

        # Create index.xml with traversal refid
        index_xml = xml_dir / "index.xml"
        # The refid points to ../secret which resolves to secret.xml
        index_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex>
  <compound refid="../secret" kind="class"><name>MaliciousClass</name></compound>
</doxygenindex>
""")

        yield str(xml_dir)

def test_path_traversal_prevention(traversal_env):
    """
    Test that path traversal attempts via malicious refid in index.xml are blocked.
    """
    async def run_test():
        engine = await DoxygenQueryEngine.create(traversal_env)

        # Attempt to query the malicious symbol
        result = engine.query_symbol("MaliciousClass")
        return result

    result = asyncio.run(run_test())

    # Assert that the result does NOT contain the secret data
    if result and "name" in result:
        assert result["name"] != "SECRET_DATA", "Path traversal vulnerability: Accessed file outside XML directory!"

    # Ideally, it should return an error
    if result:
        # If the fix works, it should return an error dict or raise an exception caught inside
        # But for now, we expect this test to FAIL because the fix is not applied yet.
        # Wait, if I want to confirm failure, I should assert the OPPOSITE?
        # No, I want the test to pass ONLY if the vulnerability is fixed.
        # So currently it should FAIL.
        assert "error" in result, f"Should return an error for path traversal attempt, got: {result}"
        err = result.get("error", "")
        assert "Security Error" in err or "Access denied" in err or "not found" in err
