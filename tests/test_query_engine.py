import pytest
import tempfile
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from doxygen_mcp.query_engine import DoxygenQueryEngine

@pytest.fixture
def xml_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def engine(xml_dir):
    # Create a basic index.xml
    index_xml = xml_dir / "index.xml"
    index_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex version="1.9.1">
  <compound refid="class_test_class" kind="class"><name>TestClass</name></compound>
  <compound refid="namespace_test_namespace" kind="namespace"><name>TestNamespace</name></compound>
  <compound refid="test_file_8h" kind="file"><name>test_file.h</name></compound>
</doxygenindex>
""")

    # Create a compound XML for TestClass
    class_xml = xml_dir / "class_test_class.xml"
    class_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class_test_class" kind="class">
    <compoundname>TestClass</compoundname>
    <location file="test_file.h" line="10" column="1"/>
    <briefdescription><para>Brief description.</para></briefdescription>
    <detaileddescription><para>Detailed description with <ref refid="other">link</ref>.</para></detaileddescription>
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
""")

    # Create a compound XML for test_file.h
    file_xml = xml_dir / "test_file_8h.xml"
    file_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="test_file_8h" kind="file">
    <compoundname>test_file.h</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="global_func">
        <name>globalFunc</name>
        <type>int</type>
        <argsstring>()</argsstring>
        <location file="test_file.h" line="5" column="1"/>
        <briefdescription><para>Global brief.</para></briefdescription>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""")

    # Create a compound XML for TestNamespace
    ns_xml = xml_dir / "namespace_test_namespace.xml"
    ns_xml.write_text("""<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="namespace_test_namespace" kind="namespace">
    <compoundname>TestNamespace</compoundname>
    <briefdescription><para>Namespace brief.</para></briefdescription>
  </compounddef>
</doxygen>
""")

    return DoxygenQueryEngine(str(xml_dir))

def test_load_index_valid(engine):
    assert "TestClass" in engine.compounds
    assert engine.compounds["TestClass"]["kind"] == "class"
    assert engine.compounds["TestClass"]["refid"] == "class_test_class"
    assert "TestNamespace" in engine.compounds
    assert "test_file.h" in engine.compounds

def test_load_index_missing(xml_dir):
    # DoxygenQueryEngine should handle missing index.xml gracefully
    engine = DoxygenQueryEngine(str(xml_dir / "nonexistent"))
    assert engine.compounds == {}

def test_load_index_invalid_xml(xml_dir):
    # DoxygenQueryEngine should handle malformed XML
    index_xml = xml_dir / "index.xml"
    index_xml.write_text("invalid xml")
    engine = DoxygenQueryEngine(str(xml_dir))
    assert engine.compounds == {}

def test_query_symbol_exact(engine):
    result = engine.query_symbol("TestClass")
    assert result is not None
    assert result["name"] == "TestClass"
    assert result["kind"] == "class"

def test_query_symbol_partial(engine):
    # Partial match should work (case-insensitive as per observed code)
    result = engine.query_symbol("testclass")
    assert result is not None
    assert result["name"] == "TestClass"

    result = engine.query_symbol("Namespace")
    assert result is not None
    assert result["name"] == "TestNamespace"

def test_query_symbol_not_found(engine):
    result = engine.query_symbol("NonExistent")
    assert result is None

def test_get_file_structure_exact(engine):
    result = engine.get_file_structure("test_file.h")
    assert len(result) == 1
    assert result[0]["name"] == "globalFunc"

def test_get_file_structure_suffix(engine):
    # In Doxygen, file compounds often have full paths or relative paths as names.
    # The code uses name.endswith(file_name)
    result = engine.get_file_structure("file.h")
    assert len(result) == 1
    assert result[0]["name"] == "globalFunc"

def test_get_file_structure_not_found(engine):
    result = engine.get_file_structure("nonexistent.h")
    assert result == []

def test_fetch_compound_details_success(engine):
    result = engine._fetch_compound_details("class_test_class")
    assert result["name"] == "TestClass"
    assert result["kind"] == "class"
    assert result["location"]["file"] == "test_file.h"
    assert result["brief"] == "Brief description."
    assert "Detailed description" in result["detailed"]
    assert len(result["members"]) == 1
    assert result["members"][0]["name"] == "testMethod"
    assert result["members"][0]["type"] == "void"
    assert result["members"][0]["args"] == "(int x)"

def test_fetch_compound_details_not_found(engine):
    result = engine._fetch_compound_details("nonexistent_refid")
    assert "error" in result
    assert "not found" in result["error"]

def test_fetch_compound_details_malformed(xml_dir, engine):
    # Create a malformed compound XML
    malformed_xml = xml_dir / "malformed.xml"
    malformed_xml.write_text("invalid xml")

    result = engine._fetch_compound_details("malformed")
    assert "error" in result
    assert "Error parsing" in result["error"]

def test_get_location(engine):
    xml_content = '<location file="test.h" line="10" column="5"/>'
    element = ET.fromstring(xml_content)
    # Since _get_location expects an element that HAS a location child
    parent = ET.Element("parent")
    parent.append(element)

    loc = engine._get_location(parent)
    assert loc["file"] == "test.h"
    assert loc["line"] == "10"
    assert loc["column"] == "5"

def test_get_location_missing(engine):
    element = ET.Element("node")
    assert engine._get_location(element) == {}

def test_get_text_recursive(engine):
    xml_content = '<briefdescription>Text <bold>child</bold> tail.</briefdescription>'
    element = ET.fromstring(xml_content)
    text = engine._get_text_recursive(element)
    assert text == "Text child tail."

def test_get_text_recursive_complex(engine):
    xml_content = """
    <detaileddescription>
      <para>Line 1.</para>
      <para>Line 2 <ref refid="ref">Ref</ref> end.</para>
    </detaileddescription>
    """
    element = ET.fromstring(xml_content)
    text = engine._get_text_recursive(element)
    # _get_text_recursive strips the final result
    assert "Line 1.Line 2 Ref end." in text.replace("\n", "").replace("  ", "")

def test_get_text_recursive_none(engine):
    assert engine._get_text_recursive(None) == ""

def test_list_all_symbols(engine):
    symbols = engine.list_all_symbols()
    assert len(symbols) == 3
    assert "TestClass" in symbols
    assert "TestNamespace" in symbols
    assert "test_file.h" in symbols

def test_list_all_symbols_filtered(engine):
    classes = engine.list_all_symbols(kind_filter="class")
    assert len(classes) == 1
    assert classes[0] == "TestClass"

    files = engine.list_all_symbols(kind_filter="file")
    assert len(files) == 1
    assert files[0] == "test_file.h"
