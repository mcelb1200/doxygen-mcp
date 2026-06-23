import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from doxygen_mcp.auditor import (
    audit_doxygen_gaps,
    audit_python_files,
    find_build_dir,
    find_nm_tool,
    scan_binary_gaps,
)


def test_audit_python_files():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a python file with some undocumented symbols
        py_content = """
class PublicClass:
    '''This has a docstring'''
    def __init__(self):
        pass
    def documented_method(self):
        '''This has a docstring'''
        pass
    def undocumented_method(self):
        pass

class UndocumentedClass:
    def method(self):
        pass

def undocumented_function():
    pass
"""
        py_file = temp_path / "test_file.py"
        py_file.write_text(py_content, encoding="utf-8")

        gaps = audit_python_files(temp_path)

        # Check gap descriptions
        symbols = [g["symbol"] for g in gaps]
        assert "PublicClass.undocumented_method" in symbols
        assert "UndocumentedClass" in symbols
        assert "undocumented_function" in symbols
        # Ensure __init__ and documented symbols are not in gaps
        assert "PublicClass.__init__" not in symbols
        assert "PublicClass.documented_method" not in symbols


def test_audit_doxygen_gaps():
    mock_engine = MagicMock()
    mock_engine.list_all_symbols.return_value = ["TestClass"]

    # Mock query_symbol return details
    mock_engine.query_symbol.return_value = {
        "name": "TestClass",
        "kind": "class",
        "location": {"file": "src/test.cpp", "line": "10"},
        "brief": "",
        "detailed": "",
        "members": [
            {
                "name": "documented_mem",
                "kind": "function",
                "location": {"file": "src/test.cpp", "line": "12"},
                "brief": "This has docs",
            },
            {
                "name": "undocumented_mem",
                "kind": "function",
                "location": {"file": "src/test.cpp", "line": "15"},
                "brief": "",
            },
        ],
    }

    gaps = audit_doxygen_gaps(mock_engine, Path("/tmp"))

    symbols = [g["symbol"] for g in gaps]
    assert "TestClass" in symbols
    assert "TestClass::undocumented_mem" in symbols
    assert "TestClass::documented_mem" not in symbols


def test_find_nm_tool():
    # Test env override
    with patch.dict(os.environ, {"DOXYGEN_NM_PATH": "/usr/bin/my-nm"}):
        with patch("os.path.exists", return_value=True):
            with patch("os.access", return_value=True):
                assert find_nm_tool() == "/usr/bin/my-nm"

    # Test PATH lookup
    with patch.dict(os.environ, {}, clear=True):
        with patch(
            "shutil.which", side_effect=lambda x: f"/path/to/{x}" if x == "nm" else None
        ):
            assert find_nm_tool() == "/path/to/nm"


def test_find_build_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Test env override
        with patch.dict(
            os.environ, {"DOXYGEN_BUILD_DIR": str(temp_path / "custom_build")}
        ):
            (temp_path / "custom_build").mkdir()
            assert find_build_dir(temp_path) == temp_path / "custom_build"

        # Test default candidate
        with patch.dict(os.environ, {}, clear=True):
            build_folder = temp_path / "build"
            build_folder.mkdir()
            assert find_build_dir(temp_path) == build_folder


@patch("subprocess.run")
def test_scan_binary_gaps(mock_run):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create mock build structure
        build_folder = temp_path / "build"
        build_folder.mkdir()
        obj_file = build_folder / "file.o"
        obj_file.write_text("dummy", encoding="utf-8")

        # Mock nm output with -A format: filepath: symbol
        mock_process = MagicMock()
        mock_process.stdout = (
            f"{str(obj_file)}:         U undefined_symbol\n{str(obj_file)}:         U __ignored_symbol\n"
        )
        mock_run.return_value = mock_process

        gaps = scan_binary_gaps("nm", build_folder)

        # Check call args
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "nm" in args
        assert "-u" in args
        assert "-A" in args
        assert str(obj_file) in args

        assert "file" in gaps
        assert "undefined_symbol" in gaps["file"]
        assert "__ignored_symbol" not in gaps["file"]
