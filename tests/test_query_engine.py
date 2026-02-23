"""
Tests for Doxygen query engine.
"""

# pylint: disable=redefined-outer-name,protected-access,import-error,wrong-import-order,unused-import

import os
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from doxygen_mcp.query_engine import DoxygenQueryEngine

@pytest.fixture
def xml_dir():
    """Fixture for a temporary XML directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def engine(xml_dir):
    """Fixture for a DoxygenQueryEngine instance"""
    # Create a basic index.xml
    index_xml = xml_dir / "index.xml"
    index_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex version="1.9.1">
  <compound refid="class_test_class" kind="class"><name>TestClass</name></compound>
  <compound refid="namespace_test_namespace" kind="namespace"><name>TestNamespace</name></compound>
  <compound refid="test_file_h" kind="file"><name>test_file.h</name>
    <member refid="test_file_h_1af62d2" kind="function"><name>test_func</name></member>
  </compound>
</doxygenindex>
""", encoding='utf-8')
    return DoxygenQueryEngine(str(xml_dir))

def test_load_index(engine):
    """Test loading the index.xml file."""
    engine._load_index()
    assert "TestClass" in engine.compounds
    assert "TestNamespace" in engine.compounds
    assert "test_file.h" in engine.compounds
    assert engine.compounds["TestClass"]["kind"] == "class"

def test_query_symbol_exact(engine):
    """Test querying a symbol with an exact match."""
    engine._load_index()
    result = engine.query_symbol("TestClass")
    assert result is not None
    assert result["name"] == "TestClass"

def test_query_symbol_case_insensitive(engine):
    """Test querying a symbol with a case-insensitive match."""
    engine._load_index()
    result = engine.query_symbol("testclass")
    assert result is not None
    assert result["name"] == "TestClass"

def test_query_symbol_partial(engine):
    """Test querying a symbol with a partial match."""
    engine._load_index()
    result = engine.query_symbol("Class")
    assert result is not None
    assert result["name"] == "TestClass"

def test_list_all_symbols(engine):
    """Test listing all symbols."""
    engine._load_index()
    symbols = engine.list_all_symbols()
    assert len(symbols) >= 3
    names = [s["name"] for s in symbols]
    assert "TestClass" in names
    assert "TestNamespace" in names

def test_list_all_symbols_filter(engine):
    """Test listing all symbols with a filter."""
    engine._load_index()
    symbols = engine.list_all_symbols(kind_filter="class")
    assert len(symbols) == 1
    assert symbols[0]["name"] == "TestClass"

def test_get_file_structure(engine):
    """Test retrieving the structure of a file."""
    engine._load_index()
    # Mock _fetch_details to return the members from the compound
    def mock_fetch(data):
        return data
    engine._fetch_details = mock_fetch

    members = engine.get_file_structure("test_file.h")
    assert len(members) == 1
    assert members["test_func"]["name"] == "test_func"

def test_fetch_compound_details(xml_dir, engine):
    """Test fetching details for a compound."""
    detail_xml = xml_dir / "class_test_class.xml"
    detail_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class_test_class" kind="class">
    <compoundname>TestClass</compoundname>
    <briefdescription><para>Brief docs</para></briefdescription>
    <detaileddescription><para>Detailed docs</para></detaileddescription>
    <location file="test.h" line="10" column="7"/>
  </compounddef>
</doxygen>
""", encoding='utf-8')

    details = engine._fetch_compound_details("class_test_class")
    assert details["brief"] == "Brief docs"
    assert details["detailed"] == "Detailed docs"
    assert details["location"]["file"] == "test.h"

def test_fetch_compound_details_not_found(engine):
    """Test fetching details for a missing compound."""
    details = engine._fetch_compound_details("nonexistent")
    assert details == {}

def test_fetch_compound_details_security(xml_dir, engine):
    """Test security against directory traversal in refid."""
    # Attempt traversal
    details = engine._fetch_compound_details("../secret")
    assert details == {}

def test_get_text(engine):
    """Test extracting text from an element."""
    elem = ET.fromstring("<name>Test</name>")
    assert engine._get_text(elem) == "Test"

def test_get_text_recursive(engine):
    """Test recursively extracting text from an element."""
    xml_str = "<desc><para>Text with <b>bold</b></para></desc>"
    elem = ET.fromstring(xml_str)
    assert engine._get_text_recursive(elem) == "Text with bold"

def test_get_text_none(engine):
    """Test extracting text from a None element."""
    assert engine._get_text(None) == ""
    assert engine._get_text_recursive(None) == ""

def test_get_location(engine):
    """Test extracting location information."""
    xml_str = '<location file="test.h" line="10" column="5"/>'
    elem = ET.fromstring(xml_str)
    loc = engine._get_location(elem)
    assert loc["file"] == "test.h"
    assert loc["line"] == "10"
    assert loc["column"] == "5"

def test_get_location_none(engine):
    """Test extracting location from a None element."""
    assert engine._get_location(None) == {}
