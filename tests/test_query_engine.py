import pytest
import os
from pathlib import Path
from doxygen_mcp.query_engine import DoxygenQueryEngine

@pytest.fixture
def sample_doxygen_xml(tmp_path):
    """Create a sample Doxygen XML structure in a temporary directory"""
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()

    # Create index.xml
    index_xml = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="index.xsd" version="1.9.1" xml:lang="en-US">
  <compound refid="classMyClass" kind="class"><name>MyClass</name></compound>
  <compound refid="namespaceMyNamespace" kind="namespace"><name>MyNamespace</name></compound>
</doxygenindex>
"""
    (xml_dir / "index.xml").write_text(index_xml)

    # Create compound XML for MyClass
    class_xml = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="compound.xsd" version="1.9.1" xml:lang="en-US">
  <compounddef id="classMyClass" kind="class" language="C++" prot="public">
    <compoundname>MyClass</compoundname>
    <briefdescription>
      <para>A brief description of MyClass.</para>
    </briefdescription>
    <detaileddescription>
      <para>A detailed description of MyClass.</para>
    </detaileddescription>
    <location file="src/MyClass.h" line="10" column="1"/>
    <sectiondef kind="public-func">
      <memberdef kind="function" id="classMyClass_1a1" prot="public" static="no" const="no" explicit="no" inline="no" virt="non-virtual">
        <name>myMethod</name>
        <type>void</type>
        <argsstring>()</argsstring>
        <briefdescription><para>Method description.</para></briefdescription>
        <location file="src/MyClass.h" line="12" column="5"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
"""
    (xml_dir / "classMyClass.xml").write_text(class_xml)

    return xml_dir

def test_query_engine_initialization(sample_doxygen_xml):
    """Test that the engine initializes and loads the index correctly"""
    engine = DoxygenQueryEngine(str(sample_doxygen_xml))
    assert "MyClass" in engine.compounds
    assert engine.compounds["MyClass"]["kind"] == "class"
    assert engine.compounds["MyClass"]["refid"] == "classMyClass"

def test_query_symbol_details(sample_doxygen_xml):
    """Test querying a symbol to get detailed information"""
    engine = DoxygenQueryEngine(str(sample_doxygen_xml))
    details = engine.query_symbol("MyClass")

    assert details is not None
    assert details["name"] == "MyClass"
    assert details["kind"] == "class"
    assert details["brief"] == "A brief description of MyClass."
    assert details["detailed"] == "A detailed description of MyClass."
    assert details["location"]["file"] == "src/MyClass.h"
    assert details["location"]["line"] == "10"

    assert len(details["members"]) == 1
    member = details["members"][0]
    assert member["name"] == "myMethod"
    assert member["kind"] == "function"
    assert member["type"] == "void"

def test_query_symbol_not_found(sample_doxygen_xml):
    """Test querying a non-existent symbol"""
    engine = DoxygenQueryEngine(str(sample_doxygen_xml))
    details = engine.query_symbol("NonExistent")
    assert details is None

def test_xxe_protection(tmp_path):
    """Explicitly test that XXE is blocked by the parser"""
    xml_dir = tmp_path / "xxe_test"
    xml_dir.mkdir()

    # Create malicious index.xml
    # Note: We can't easily check for file inclusion because defusedxml raises an exception
    # before we can inspect the result. We just want to ensure it raises Forbidden.

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("SECRET")

    index_xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE doxygenindex [
  <!ENTITY xxe SYSTEM "file://{secret_file}">
]>
<doxygenindex>
  <compound refid="test" kind="class"><name>&xxe;</name></compound>
</doxygenindex>
"""
    (xml_dir / "index.xml").write_text(index_xml)

    # We expect the engine to catch the exception and print an error,
    # OR we can inspect captured stdout if we want to be strict.
    # The current implementation catches Exception and prints "Error loading index: ..."
    # So the compounds dict should be empty.

    # However, to be more precise, let's just assert that compounds is empty
    # and maybe verify that we didn't crash.

    engine = DoxygenQueryEngine(str(xml_dir))
    assert len(engine.compounds) == 0
