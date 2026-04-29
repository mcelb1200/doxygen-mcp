
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

@pytest.mark.asyncio
async def test_update_ignore_file_security_regex(tmp_path):
    """Test that special characters are rejected by regex."""
    dangerous_paths = [
        "docs/;rm",
        "docs/$HOME",
        "docs/`whoami`",
        "docs/|",
        "docs/ ",
    ]
    for path in dangerous_paths:
        result = await update_ignore_file(tmp_path, path)
        assert result is False, f"Should have rejected {path}"

@pytest.mark.asyncio
async def test_update_ignore_file_security_traversal_v2(tmp_path):
    """Test that parent directory references are rejected in various positions."""
    dangerous_paths = [
        "../outside_project",
        "foo/../bar",
        "subdir/..",
        "../../etc/passwd",
        "./../hidden",
        "file..name"
    ]

    for path_to_ignore in dangerous_paths:
        result = await update_ignore_file(tmp_path, path_to_ignore)

        ignore_file = tmp_path / ".gitignore"
        if ignore_file.exists():
            content = ignore_file.read_text(encoding="utf-8")
            assert path_to_ignore not in content, f"Traversal sequence {path_to_ignore} allowed in .gitignore"

        assert result is False, f"Function should return False for traversal input: {path_to_ignore}"

@pytest.mark.asyncio
async def test_update_ignore_file_dots_allowed(tmp_path):
    """Test that entries with dots but not traversal are still allowed."""
    safe_paths = [
        ".hidden",
        "file.ext",
        "dir.with.dots/file",
        "dot.dot"
    ]

    for path_to_ignore in safe_paths:
        result = await update_ignore_file(tmp_path, path_to_ignore)
        assert result is True, f"Should have allowed {path_to_ignore}"

    ignore_file = tmp_path / ".gitignore"
    content = ignore_file.read_text(encoding="utf-8")
    for path_to_ignore in safe_paths:
        assert path_to_ignore in content

@pytest.mark.asyncio
async def test_update_ignore_file_permission_denied(tmp_path):
    """Test that PermissionError (an OSError) is caught when updating .gitignore."""
    ignore_file = tmp_path / ".gitignore"
    ignore_file.write_text("existing_entry\n", encoding="utf-8")

    # Make the file read-only
    ignore_file.chmod(0o444)

    try:
        path_to_ignore = "new_entry"
        # This should attempt to open for "r+" which should fail with PermissionError
        result = await update_ignore_file(tmp_path, path_to_ignore)

        # Should still return False because of the 'except OSError: pass'
        assert result is False
    finally:
        # Restore permissions so tmp_path can be cleaned up
        ignore_file.chmod(0o644)

@pytest.mark.asyncio
async def test_update_ignore_file_logic_error_propagation(tmp_path, monkeypatch):
    """
    Test that non-OSError exceptions (like logic errors) are NOT caught and propagate.
    We'll mock Path.is_symlink to raise a non-OSError exception.
    """
    from pathlib import Path

    original_is_symlink = Path.is_symlink

    def mock_is_symlink(self):
        # Only raise for our specific test directory to avoid breaking pytest
        if str(self).startswith(str(tmp_path)):
            raise AttributeError("Simulated logic error")
        return original_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", mock_is_symlink)

    path_to_ignore = "some_path"
    # Now this should raise AttributeError instead of returning False
    with pytest.raises(AttributeError, match="Simulated logic error"):
        await update_ignore_file(tmp_path, path_to_ignore)
