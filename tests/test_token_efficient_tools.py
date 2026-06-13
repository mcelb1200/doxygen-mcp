"""
Unit tests for the new token-efficient Doxygen MCP tools.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from doxygen_mcp.query_engine import DoxygenQueryEngine


@pytest.fixture
def test_env():
    """Create a temporary Doxygen workspace with mock XML files and source code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        xml_dir = tmp_path / "xml"
        xml_dir.mkdir()

        # Write index.xml
        index_xml = xml_dir / "index.xml"
        index_xml.write_text(
            """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex version="1.9.1">
  <compound refid="class_calculator" kind="class"><name>Calculator</name></compound>
  <compound refid="main_8py" kind="file"><name>main.py</name></compound>
</doxygenindex>
""",
            encoding="utf-8",
        )

        # Write Calculator class XML
        class_xml = xml_dir / "class_calculator.xml"
        class_xml.write_text(
            """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class_calculator" kind="class">
    <compoundname>Calculator</compoundname>
    <location file="main.py" line="5" column="1" bodystart="5" bodyend="15"/>
    <sectiondef kind="public-func">
      <memberdef kind="function" id="class_calculator_1add">
        <name>add</name>
        <type>int</type>
        <argsstring>(int a, int b)</argsstring>
        <location file="main.py" line="8" column="5" bodystart="8" bodyend="10"/>
        <references refid="global_helper">global_helper</references>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            encoding="utf-8",
        )

        # Write main.py file XML
        file_xml = xml_dir / "main_8py.xml"
        file_xml.write_text(
            """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="main_8py" kind="file">
    <compoundname>main.py</compoundname>
    <innerclass refid="class_calculator">Calculator</innerclass>
    <sectiondef kind="func">
      <memberdef kind="function" id="global_helper">
        <name>global_helper</name>
        <type>int</type>
        <argsstring>(int x)</argsstring>
        <location file="main.py" line="2" column="1" bodystart="2" bodyend="4"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            encoding="utf-8",
        )

        # Create mock source file main.py
        main_py = tmp_path / "main.py"
        main_py.write_text(
            """
def global_helper(x):
    return x + 1

class Calculator:


    def add(self, a, b):
        return global_helper(a + b)
""",
            encoding="utf-8",
        )

        # Initialize engine
        engine = DoxygenQueryEngine(str(xml_dir))
        engine.search_index.repo_root = tmp_path
        engine._load_index()

        yield engine, tmp_path


def test_get_file_structure_with_class(test_env):
    """Test get_file_structure correctly collects all symbols in a file."""
    engine, _ = test_env
    struct = engine.get_file_structure("main.py")

    names = {s["name"] for s in struct}
    assert "Calculator" in names
    assert "add" in names
    assert "global_helper" in names


def test_get_file_skeleton(test_env):
    """Test get_file_skeleton generates expected pass-stubbed signatures."""
    engine, _ = test_env
    skeleton = engine.get_file_skeleton("main.py")

    assert "def global_helper(x):" in skeleton
    assert "pass" in skeleton
    assert "def add(self, a, b):" in skeleton


def test_trace_call_path(test_env):
    """Test trace_call_path outputs chronological call execution flow."""
    engine, _ = test_env
    path_trace = engine.trace_call_path("add")

    assert "[STEP 1] Caller: Calculator::add" in path_trace
    assert "[STEP 2] Callee: global_helper" in path_trace
    assert "def add(self, a, b):" in path_trace
    assert "def global_helper(x):" in path_trace


def test_get_virtual_diff_modified(test_env):
    """Test get_virtual_diff identifies modified method signatures."""
    engine, tmp_path = test_env

    # Modify main.py: change signature of add (add third parameter)
    main_py = tmp_path / "main.py"
    main_py.write_text(
        """
def global_helper(x):
    return x + 1

class Calculator:


    def add(self, a, b, c):
        return global_helper(a + b + c)
""",
        encoding="utf-8",
    )

    # Mock git status --porcelain
    mock_run = Mock()
    mock_run.return_value = Mock(stdout=" M main.py\n", returncode=0)

    with patch("subprocess.run", mock_run):
        diff = engine.get_virtual_diff(str(tmp_path))

    assert "modified_files" in diff
    assert len(diff["modified_files"]) == 1
    mod_file = diff["modified_files"][0]
    assert mod_file["file"] == "main.py"
    assert len(mod_file["modified_signatures"]) == 1
    assert mod_file["modified_signatures"][0]["old"] == "add(int a, int b)"
    assert "add(self, a, b, c)" in mod_file["modified_signatures"][0]["new"]
