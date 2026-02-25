
import pytest
import os
from pathlib import Path
from doxygen_mcp.utils import update_ignore_file

@pytest.mark.asyncio
async def test_update_ignore_file_security_newline(tmp_path):
    """Test that newlines are rejected in .gitignore entries."""
    path_to_ignore = "safe_entry\nunsafe_entry"
    result = await update_ignore_file(tmp_path, path_to_ignore)

    ignore_file = tmp_path / ".gitignore"
    if ignore_file.exists():
        content = ignore_file.read_text(encoding="utf-8")
        assert "unsafe_entry" not in content, "Newlines allowed injection into .gitignore"
        assert "safe_entry" not in content, "Should reject the entire entry if it contains newlines"

    assert result is False, "Function should return False for invalid input"

@pytest.mark.asyncio
async def test_update_ignore_file_security_traversal(tmp_path):
    """Test that parent directory references are rejected."""
    path_to_ignore = "../outside_project"
    result = await update_ignore_file(tmp_path, path_to_ignore)

    ignore_file = tmp_path / ".gitignore"
    if ignore_file.exists():
        content = ignore_file.read_text(encoding="utf-8")
        assert "../outside_project" not in content, "Traversal sequence allowed in .gitignore"

    assert result is False, "Function should return False for traversal input"

@pytest.mark.asyncio
async def test_update_ignore_file_valid(tmp_path):
    """Test that valid entries are accepted."""
    path_to_ignore = "docs/"
    result = await update_ignore_file(tmp_path, path_to_ignore)

    assert result is True
    ignore_file = tmp_path / ".gitignore"
    assert ignore_file.exists()
    content = ignore_file.read_text(encoding="utf-8")
    assert "docs/" in content
