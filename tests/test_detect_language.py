"""
Tests for detect_primary_language utility.
"""
# pylint: disable=import-error
from pathlib import Path
import pytest
from doxygen_mcp.utils import detect_primary_language

def test_detect_python(tmp_path):
    """Test detection of Python project."""
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def foo(): pass", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "python"

def test_detect_cpp(tmp_path):
    """Test detection of C++ project."""
    (tmp_path / "main.cpp").write_text("int main() {}", encoding="utf-8")
    (tmp_path / "header.hpp").write_text("// header", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "cpp"

def test_detect_c(tmp_path):
    """Test detection of C project."""
    (tmp_path / "main.c").write_text("int main() {}", encoding="utf-8")
    (tmp_path / "header.h").write_text("// header", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "c"

def test_detect_mixed_cpp_dominant(tmp_path):
    """Test detection when C++ files outnumber others."""
    (tmp_path / "main.cpp").write_text("int main() {}", encoding="utf-8")
    (tmp_path / "header.hpp").write_text("// header", encoding="utf-8")
    (tmp_path / "script.py").write_text("print('hi')", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "cpp"

def test_detect_one_level_deep(tmp_path):
    """Test detection of files in one level of subdirectories."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.cpp").write_text("int main() {}", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "cpp"

def test_detect_two_levels_deep(tmp_path):
    """Test that files two levels deep are NOT detected."""
    # detect_primary_language uses glob("*") and glob("*/*")
    deep = tmp_path / "src" / "deep"
    deep.mkdir(parents=True)
    (deep / "main.cpp").write_text("int main() {}", encoding="utf-8")
    # Should return mixed because it doesn't find the .cpp file
    assert detect_primary_language(tmp_path) == "mixed"

def test_detect_empty(tmp_path):
    """Test detection in an empty directory."""
    assert detect_primary_language(tmp_path) == "mixed"

def test_detect_no_matching_extensions(tmp_path):
    """Test detection when no known extensions are present."""
    (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "mixed"

def test_detect_case_insensitive(tmp_path):
    """Test that extension matching is case-insensitive."""
    (tmp_path / "MAIN.CPP").write_text("int main() {}", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "cpp"

def test_detect_go(tmp_path):
    """Test detection of Go project."""
    (tmp_path / "main.go").write_text("package main", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "go"

def test_detect_rust(tmp_path):
    """Test detection of Rust project."""
    (tmp_path / "main.rs").write_text("fn main() {}", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "rust"

def test_detect_javascript(tmp_path):
    """Test detection of JavaScript/TypeScript project."""
    (tmp_path / "index.js").write_text("console.log()", encoding="utf-8")
    (tmp_path / "app.ts").write_text("let x: number", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "javascript"

def test_detect_java(tmp_path):
    """Test detection of Java project."""
    (tmp_path / "Main.java").write_text("class Main {}", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "java"

def test_detect_csharp(tmp_path):
    """Test detection of C# project."""
    (tmp_path / "Program.cs").write_text("class Program {}", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "csharp"

def test_detect_php(tmp_path):
    """Test detection of PHP project."""
    (tmp_path / "index.php").write_text("<?php echo 'hi'; ?>", encoding="utf-8")
    assert detect_primary_language(tmp_path) == "php"

def test_detect_exception_handling(tmp_path):
    """Test that exceptions during scanning return mixed."""
    # We can pass a non-directory path to trigger an exception in glob() or similar
    file_path = tmp_path / "not_a_dir"
    file_path.write_text("content", encoding="utf-8")
    assert detect_primary_language(file_path) == "mixed"
