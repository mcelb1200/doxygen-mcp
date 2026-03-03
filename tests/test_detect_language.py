"""
Tests for detect_primary_language function.
"""
# pylint: disable=import-error, redefined-outer-name
import tempfile
from pathlib import Path

import pytest  # pylint: disable=import-error

from doxygen_mcp.utils import detect_primary_language

@pytest.fixture
def temp_project_dir():
    """Fixture for a temporary project directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

def test_detect_language_empty(temp_project_dir):
    """Test detect_primary_language on an empty directory."""
    lang = detect_primary_language(temp_project_dir)
    assert lang == "mixed"

def test_detect_language_single_file(temp_project_dir):
    """Test detect_primary_language with a single recognized file."""
    (temp_project_dir / "main.py").write_text("print('hello')", encoding="utf-8")

    lang = detect_primary_language(temp_project_dir)
    assert lang == "python"

def test_detect_language_mixed_dominance(temp_project_dir):
    """Test that detect_primary_language selects the most frequent language."""
    # 2 python files
    (temp_project_dir / "main.py").touch()
    (temp_project_dir / "utils.py").touch()
    # 1 cpp file
    (temp_project_dir / "main.cpp").touch()

    lang = detect_primary_language(temp_project_dir)
    assert lang == "python"

def test_detect_language_case_insensitive(temp_project_dir):
    """Test that detect_primary_language ignores extension case."""
    (temp_project_dir / "file1.CPP").touch()
    (temp_project_dir / "file2.HPP").touch()
    (temp_project_dir / "file3.cpp").touch()

    lang = detect_primary_language(temp_project_dir)
    assert lang == "cpp"

def test_detect_language_depth(temp_project_dir):
    """Test that detect_primary_language scans root and one level deep, but not deeper."""
    # Root level (1 python)
    (temp_project_dir / "root.py").touch()

    # One level deep (2 cpp)
    subdir1 = temp_project_dir / "src"
    subdir1.mkdir()
    (subdir1 / "file1.cpp").touch()
    (subdir1 / "file2.cpp").touch()

    # Two levels deep (10 java files, shouldn't be counted)
    subdir2 = subdir1 / "internal"
    subdir2.mkdir()
    for i in range(10):
        (subdir2 / f"file{i}.java").touch()

    lang = detect_primary_language(temp_project_dir)
    assert lang == "cpp"  # Should be cpp (2) vs python (1), ignoring java (10)

def test_detect_language_multiple_extensions(temp_project_dir):
    """Test that multiple extensions map to the same language."""
    # 4 javascript files with different extensions
    (temp_project_dir / "file1.js").touch()
    (temp_project_dir / "file2.ts").touch()
    (temp_project_dir / "file3.jsx").touch()
    (temp_project_dir / "file4.tsx").touch()

    # 3 python files
    (temp_project_dir / "file1.py").touch()
    (temp_project_dir / "file2.py").touch()
    (temp_project_dir / "file3.py").touch()

    lang = detect_primary_language(temp_project_dir)
    assert lang == "javascript"

def test_detect_language_ignore_directories(temp_project_dir):
    """Test that directories with extensions are ignored."""
    # 1 c file
    (temp_project_dir / "main.c").touch()

    # A directory named .py
    (temp_project_dir / "test.py").mkdir()

    lang = detect_primary_language(temp_project_dir)
    assert lang == "c"
