import pytest
import asyncio
import os
from pathlib import Path
from doxygen_mcp.query_engine import DoxygenQueryEngine

def test_path_traversal_refid(tmp_path):
    async def run_test():
        # Setup directory structure
        base_dir = tmp_path / "base"
        base_dir.mkdir()

        xml_dir = base_dir / "xml"
        xml_dir.mkdir()

        # Create a secret file outside xml_dir
        secret_file = base_dir / "secret.xml"
        secret_content = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
        <doxygen>
          <compounddef kind="file">
            <compoundname>SECRET_FILE</compoundname>
          </compounddef>
        </doxygen>
        """
        secret_file.write_text(secret_content)

        # Create a VALID file inside xml_dir
        valid_file = xml_dir / "valid.xml"
        valid_content = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
        <doxygen>
          <compounddef kind="file">
            <compoundname>VALID_FILE</compoundname>
            <briefdescription><para>This is a valid file.</para></briefdescription>
            <detaileddescription></detaileddescription>
          </compounddef>
        </doxygen>
        """
        valid_file.write_text(valid_content)

        # Create index.xml with a malicious refid AND a valid refid
        index_content = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
        <doxygenindex>
          <compound refid="../secret" kind="file">
            <name>MaliciousFile</name>
          </compound>
          <compound refid="valid" kind="file">
            <name>ValidFile</name>
          </compound>
        </doxygenindex>
        """
        (xml_dir / "index.xml").write_text(index_content)

        # Initialize engine
        engine = await DoxygenQueryEngine.create(str(xml_dir))

        # Query the malicious symbol
        result_malicious = engine.query_symbol("MaliciousFile")

        # Query the valid symbol
        result_valid = engine.query_symbol("ValidFile")

        return result_malicious, result_valid

    result_malicious, result_valid = asyncio.run(run_test())

    # Verify the malicious file is blocked
    print(f"Malicious Result: {result_malicious}")
    assert result_malicious is not None
    assert "error" in result_malicious
    assert "Security Error" in result_malicious["error"]
    assert "SECRET_FILE" not in str(result_malicious)

    # Verify the valid file is accessible
    print(f"Valid Result: {result_valid}")
    assert result_valid is not None
    assert "error" not in result_valid
    assert result_valid.get("name") == "VALID_FILE"
