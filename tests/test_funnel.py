import xml.etree.ElementTree as ET
from pathlib import Path
import tempfile
import pytest
from doxygen_mcp.funnel import minify_xml_file

def test_minify_xml_file():
    content = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class1">
    <collaborationgraph>Graph</collaborationgraph>
    <briefdescription></briefdescription>
    <detaileddescription>
      <para>Some text</para>
    </detaileddescription>
    <memberdef>
      <name>member1</name>
      <briefdescription>
      </briefdescription>
      <listofallmembers>
        <member>1</member>
      </listofallmembers>
    </memberdef>
  </compounddef>
</doxygen>
"""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode='w', encoding='utf-8') as f:
        f.write(content)
        tmp_path = f.name

    try:
        assert minify_xml_file(tmp_path) is True

        tree = ET.parse(tmp_path)
        root = tree.getroot()

        # Check collaborationgraph removed
        assert root.find(".//collaborationgraph") is None
        # Check listofallmembers removed
        assert root.find(".//listofallmembers") is None

        # Check empty briefdescription removed
        # Note: root.findall(".//briefdescription")
        briefs = root.findall(".//briefdescription")
        for b in briefs:
            assert len(b) > 0 or (b.text and b.text.strip() != "")

        # Check detaileddescription with content remains
        assert root.find(".//detaileddescription") is not None

    finally:
        Path(tmp_path).unlink()

if __name__ == "__main__":
    test_minify_xml_file()
    print("Test passed!")
