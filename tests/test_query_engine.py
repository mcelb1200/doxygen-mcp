"""
Unit tests for the DoxygenQueryEngine.
"""
# pylint: disable=import-error, redefined-outer-name, protected-access
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from doxygen_mcp.query_engine import DoxygenQueryEngine

@pytest.fixture
def xml_dir():
    """Fixture for a temporary XML directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def engine(xml_dir):
    """Fixture for a DoxygenQueryEngine instance with pre-populated data."""
    # Create a basic index.xml
    index_xml = xml_dir / "index.xml"
    index_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex version="1.9.1">
  <compound refid="class_test_class" kind="class"><name>TestClass</name></compound>
  <compound refid="namespace_test_namespace" kind="namespace"><name>TestNamespace</name></compound>
  <compound refid="test_file_8h" kind="file"><name>test_file.h</name></compound>
</doxygenindex>
""", encoding="utf-8")

    # Create a compound XML for TestClass
    class_xml = xml_dir / "class_test_class.xml"
    class_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class_test_class" kind="class">
    <compoundname>TestClass</compoundname>
    <location file="test_file.h" line="10" column="1"/>
    <briefdescription><para>Brief description.</para></briefdescription>
    <detaileddescription><para>Detailed description.</para></detaileddescription>
    <sectiondef kind="public-func">
      <memberdef kind="function" id="class_test_class_1method">
        <name>testMethod</name>
        <type>void</type>
        <argsstring>(int x)</argsstring>
        <location file="test_file.h" line="15" column="5"/>
        <briefdescription><para>Method brief.</para></briefdescription>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""", encoding="utf-8")

    query_engine = DoxygenQueryEngine(str(xml_dir))
    query_engine._load_index()
    return query_engine

def test_load_index_valid(engine):
    """Test loading a valid index.xml."""
    assert "TestClass" in engine.compounds
    assert engine.compounds["TestClass"]["kind"] == "class"
    assert engine.compounds["TestClass"]["refid"] == "class_test_class"

def test_load_index_missing(xml_dir):
    """Test loading when index.xml is missing."""
    engine = DoxygenQueryEngine(str(xml_dir / "nonexistent"))
    engine._load_index()
    assert not engine.compounds

def test_load_index_invalid_xml(xml_dir):
    """Test loading when index.xml is malformed."""
    index_xml = xml_dir / "index.xml"
    index_xml.write_text("invalid xml", encoding="utf-8")
    engine = DoxygenQueryEngine(str(xml_dir))
    engine._load_index()
    assert not engine.compounds

def test_query_symbol_exact(engine):
    """Test exact symbol query."""
    result = engine.query_symbol("TestClass")
    assert result is not None
    assert result["name"] == "TestClass"
    assert result["kind"] == "class"

def test_query_symbol_partial(engine):
    """Test partial and case-insensitive symbol query."""
    result = engine.query_symbol("testclass")
    assert result is not None
    assert result["name"] == "TestClass"

def test_query_symbol_not_found(engine):
    """Test query for non-existent symbol."""
    result = engine.query_symbol("NonExistent")
    assert result is None

def test_get_file_structure_exact(engine):
    """Test retrieving file structure with exact match."""
    result = engine.get_file_structure("test_file.h")
    assert result == []

def test_get_file_structure_not_found(engine):
    """Test retrieving file structure for non-existent file."""
    result = engine.get_file_structure("nonexistent.h")
    assert not result

def test_fetch_compound_details_not_found(engine):
    """Test fetching details for non-existent refid."""
    result = engine._fetch_compound_details("nonexistent_refid")
    assert "error" in result
    assert "not found" in result["error"]

def test_get_location(engine):
    """Test location extraction."""
    xml_content = '<location file="test.h" line="10" column="5"/>'
    element = ET.fromstring(xml_content)
    parent = ET.Element("parent")
    parent.append(element)
    loc = engine._get_location(parent)
    assert loc["file"] == "test.h"
    assert loc["line"] == "10"
    assert loc["column"] == "5"

def test_get_location_missing(engine):
    """Test location extraction when missing."""
    element = ET.Element("node")
    assert engine._get_location(element) == {}

def test_get_text_recursive(engine):
    """Test recursive text extraction."""
    xml_content = '<briefdescription>Text <bold>child</bold> tail.</briefdescription>'
    element = ET.fromstring(xml_content)
    text = engine._get_text_recursive(element)
    assert text == "Text child tail."

def test_get_text_recursive_none(engine):
    """Test recursive text extraction for None."""
    assert engine._get_text_recursive(None) == ""

def test_list_all_symbols(engine):
    """Test listing all symbols."""
    symbols = engine.list_all_symbols()
    assert len(symbols) == 3
    assert "TestClass" in symbols
    assert "TestNamespace" in symbols
    assert "test_file.h" in symbols

def test_list_all_symbols_filtered(engine):
    """Test filtered symbol listing."""
    classes = engine.list_all_symbols(kind_filter="class")
    assert len(classes) == 1
    assert classes[0] == "TestClass"
    files = engine.list_all_symbols(kind_filter="file")
    assert len(files) == 1
    assert files[0] == "test_file.h"
