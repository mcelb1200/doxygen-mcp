import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

# Add src to path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from doxygen_mcp.auditor import check_doxygen_parity
from doxygen_mcp.query_engine import DoxygenQueryEngine
from doxygen_mcp.server import (
    doxy_parity_check,
    doxy_references,
    doxy_refresh_delta,
    doxy_rename_impact,
)

INDEX_XML_CONTENT = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="index.xsd" version="1.9.4" xml:lang="en-US">
  <compound refid="class_calculator" kind="class"><name>Calculator</name>
    <member refid="class_calculator_1a1" kind="function"><name>add</name></member>
    <member refid="class_calculator_1a2" kind="function"><name>subtract</name></member>
  </compound>
  <compound refid="calculator_8h" kind="file"><name>calculator.h</name>
  </compound>
</doxygenindex>
"""

CALCULATOR_XML_CONTENT = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="compound.xsd" version="1.9.4" xml:lang="en-US">
  <compounddef id="class_calculator" kind="class" language="C++" prot="public">
    <compoundname>Calculator</compoundname>
    <sectiondef kind="public-func">
      <memberdef kind="function" id="class_calculator_1a1" prot="public" static="no" const="no" explicit="no" inline="no" virt="non-virtual">
        <type>double</type>
        <definition>double Calculator::add</definition>
        <argsstring>(double a, double b)</argsstring>
        <name>add</name>
        <param>
          <type>double</type>
          <declname>a</declname>
        </param>
        <param>
          <type>double</type>
          <declname>b</declname>
        </param>
        <location file="calculator.h" line="10" column="1"/>
        <detaileddescription>
          <para>
            <parameterlist kind="param">
              <parameteritem>
                <parameternamelist>
                  <parametername>a</parametername>
                </parameternamelist>
                <parameterdescription><para>First number</para></parameterdescription>
              </parameteritem>
              <parameteritem>
                <parameternamelist>
                  <parametername>b_mismatched</parametername>
                </parameternamelist>
                <parameterdescription><para>Second number</para></parameterdescription>
              </parameteritem>
            </parameterlist>
          </para>
        </detaileddescription>
        <referencedby refid="class_calculator_1a2" compoundref="calculator.h" startline="15" endline="20">Calculator::subtract</referencedby>
      </memberdef>
      <memberdef kind="function" id="class_calculator_1a2" prot="public" static="no" const="no" explicit="no" inline="no" virt="non-virtual">
        <type>double</type>
        <definition>double Calculator::subtract</definition>
        <argsstring>(double a, double b)</argsstring>
        <name>subtract</name>
        <param>
          <type>double</type>
          <declname>a</declname>
        </param>
        <param>
          <type>double</type>
          <declname>b</declname>
        </param>
        <location file="calculator.h" line="15" column="1"/>
        <detaileddescription/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
"""


@pytest.fixture
def temp_xml_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        xml_dir = Path(tmpdir) / "xml"
        xml_dir.mkdir()

        # Write index.xml
        (xml_dir / "index.xml").write_text(INDEX_XML_CONTENT, encoding="utf-8")

        # Write compound XML
        (xml_dir / "class_calculator.xml").write_text(
            CALCULATOR_XML_CONTENT, encoding="utf-8"
        )

        # Write source code file for references
        src_content = (
            "\n" * 14
            + "double Calculator::subtract(double a, double b) {\n    return add(a, -b);\n}\n"
        )
        (xml_dir / "calculator.h").write_text(src_content, encoding="utf-8")

        yield str(xml_dir)


@pytest.mark.asyncio
async def test_member_parent_mapping(temp_xml_dir):
    engine = await DoxygenQueryEngine.create(temp_xml_dir)
    assert engine._member_parent_map["class_calculator_1a1"] == "class_calculator"
    assert engine._member_parent_map["class_calculator_1a2"] == "class_calculator"


@pytest.mark.asyncio
async def test_find_symbol_definitions(temp_xml_dir):
    engine = await DoxygenQueryEngine.create(temp_xml_dir)
    defs = engine.find_symbol_definitions("Calculator")
    assert len(defs) == 1
    assert defs[0]["name"] == "Calculator"
    assert not defs[0]["is_member"]

    defs_member = engine.find_symbol_definitions("add")
    assert len(defs_member) == 1
    assert defs_member[0]["name"] == "add"
    assert defs_member[0]["is_member"]
    assert defs_member[0]["parent_name"] == "Calculator"


@pytest.mark.asyncio
async def test_find_references(temp_xml_dir):
    engine = await DoxygenQueryEngine.create(temp_xml_dir)
    refs = engine.find_references("add")
    assert len(refs) == 1
    assert "add" in refs[0]["content"]
    assert refs[0]["caller"] == "Calculator::subtract"
    assert refs[0]["line"] == 16  # relative line matching


@pytest.mark.asyncio
async def test_check_doxygen_parity(temp_xml_dir):
    engine = await DoxygenQueryEngine.create(temp_xml_dir)
    mismatches = check_doxygen_parity(engine)

    # We expect mismatch for 'b_mismatched' vs 'b', and missing for 'b'
    assert len(mismatches) > 0
    kinds = [m["kind"] for m in mismatches]
    assert "parameter_mismatch" in kinds or "parameter_redundant" in kinds


@pytest.mark.asyncio
@patch("doxygen_mcp.server.resolve_project_path")
@patch("doxygen_mcp.server._find_xml_dir")
async def test_doxy_rename_impact(mock_xml_dir, mock_resolve_path, temp_xml_dir):
    mock_resolve_path.return_value = Path("/tmp/fake_project")
    mock_xml_dir.return_value = temp_xml_dir

    # Clear cache to reload with mock directory
    DoxygenQueryEngine.clear_cache()

    impact = await doxy_rename_impact("add", "/tmp/fake_project")
    assert impact["found"]
    assert len(impact["definitions"]) == 1
    assert len(impact["references"]) == 1
    assert impact["references"][0]["caller"] == "Calculator::subtract"


@pytest.mark.asyncio
@patch("doxygen_mcp.server.resolve_project_path")
@patch("doxygen_mcp.server._find_xml_dir")
async def test_doxy_parity_check_tool(mock_xml_dir, mock_resolve_path, temp_xml_dir):
    mock_resolve_path.return_value = Path("/tmp/fake_project")
    mock_xml_dir.return_value = temp_xml_dir
    DoxygenQueryEngine.clear_cache()

    res = await doxy_parity_check("/tmp/fake_project")
    assert len(res) > 0
    assert any(
        m["kind"] in ("parameter_mismatch", "parameter_redundant", "parameter_missing")
        for m in res
    )


@pytest.mark.asyncio
@patch("doxygen_mcp.server.resolve_project_path")
@patch("doxygen_mcp.server._find_xml_dir")
@patch("doxygen_mcp.server.get_doxygen_executable")
@patch("asyncio.create_subprocess_exec")
async def test_doxy_refresh_delta_tool(
    mock_exec, mock_doxy_exe, mock_xml_dir, mock_resolve_path, temp_xml_dir
):
    mock_resolve_path.return_value = Path("/tmp/fake_project")
    mock_xml_dir.return_value = temp_xml_dir
    mock_doxy_exe.return_value = "doxygen"

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_exec.return_value = mock_process

    with tempfile.TemporaryDirectory() as fake_project:
        fake_proj_path = Path(fake_project)
        mock_resolve_path.return_value = fake_proj_path

        (fake_proj_path / "Doxyfile").write_text("", encoding="utf-8")

        target_file = fake_proj_path / "test.cpp"
        target_file.write_text("", encoding="utf-8")

        fake_xml_dir = fake_proj_path / "docs" / "xml"
        fake_xml_dir.mkdir(parents=True)
        (fake_xml_dir / "index.xml").write_text(INDEX_XML_CONTENT, encoding="utf-8")
        mock_xml_dir.return_value = str(fake_xml_dir)

        async def mock_communicate():
            temp_xml_out = fake_proj_path / ".doxy_delta_temp" / "xml"
            temp_xml_out.mkdir(parents=True, exist_ok=True)
            (temp_xml_out / "class_calculator.xml").write_text(
                CALCULATOR_XML_CONTENT, encoding="utf-8"
            )
            (temp_xml_out / "index.xml").write_text(INDEX_XML_CONTENT, encoding="utf-8")
            return b"", b""

        mock_process.communicate.side_effect = mock_communicate

        res = await doxy_refresh_delta(str(target_file), str(fake_proj_path))
        assert "Delta refresh completed successfully" in res
