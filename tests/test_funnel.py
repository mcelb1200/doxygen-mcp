"""
Tests for Doxygen context funnel utilities.
"""
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

from doxygen_mcp.funnel import minify_xml_file

def test_minify_standard_tags():
    """Test removal of low-signal Doxygen tags."""
    xml_content = """<?xml version='1.0' encoding='utf-8'?>
<doxygen>
  <compounddef>
    <collaborationgraph>
      <node>1</node>
    </collaborationgraph>
    <listofallmembers>
      <member>foo</member>
    </listofallmembers>
    <briefdescription>
      <para>Some description</para>
    </briefdescription>
  </compounddef>
</doxygen>
"""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode='w', encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name

    try:
        success = minify_xml_file(temp_path)
        assert success is True

        tree = ET.parse(temp_path)
        root = tree.getroot()

        assert root.find(".//collaborationgraph") is None
        assert root.find(".//listofallmembers") is None
        assert root.find(".//briefdescription") is not None
        assert root.find(".//para").text == "Some description"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_minify_empty_descriptions():
    """Test stripping of empty description tags."""
    xml_content = """<?xml version='1.0' encoding='utf-8'?>
<doxygen>
  <compounddef>
    <briefdescription>
    </briefdescription>
    <detaileddescription></detaileddescription>
    <important>Keep this</important>
  </compounddef>
</doxygen>
"""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode='w', encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name

    try:
        success = minify_xml_file(temp_path)
        assert success is True

        tree = ET.parse(temp_path)
        root = tree.getroot()

        assert root.find(".//briefdescription") is None
        assert root.find(".//detaileddescription") is None
        assert root.find(".//important") is not None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_minify_whitespace_collapse():
    """Test collapsing of whitespace-only text and tails."""
    xml_content = """<root>
  <element>   </element>
  <another>Value</another>
</root>"""

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode='w', encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name

    try:
        success = minify_xml_file(temp_path)
        assert success is True

        # Read file directly to check for whitespace removal if possible,
        # but ET.write might re-introduce some depending on how it's called.
        # The code sets elem.text = "" if it was whitespace-only.

        tree = ET.parse(temp_path)
        root = tree.getroot()

        elem = root.find("element")
        assert elem.text == "" or elem.text is None

        # ET.write usually doesn't add much whitespace unless told to.
        # The key is that the logic inside minify_xml_file was executed.
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_minify_already_minified():
    """Test behavior with already minified XML."""
    xml_content = "<?xml version='1.0' encoding='utf-8'?><root><node>value</node></root>"

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode='w', encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name

    try:
        success = minify_xml_file(temp_path)
        assert success is True

        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "<node>value</node>" in content
        assert "<root>" in content
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_minify_no_elements():
    """Test behavior with XML containing only a root element."""
    xml_content = "<?xml version='1.0' encoding='utf-8'?><root />"

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode='w', encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name

    try:
        success = minify_xml_file(temp_path)
        assert success is True

        tree = ET.parse(temp_path)
        assert tree.getroot().tag == "root"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_minify_invalid_xml():
    """Test behavior with invalid XML."""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode='w', encoding='utf-8') as f:
        f.write("not xml")
        temp_path = f.name

    try:
        success = minify_xml_file(temp_path)
        assert success is False
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_minify_nonexistent_file():
    """Test behavior with non-existent file."""
    success = minify_xml_file("/tmp/nonexistent_file_12345.xml")
    assert success is False
