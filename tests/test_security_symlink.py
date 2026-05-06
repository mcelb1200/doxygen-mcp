"""
Tests for verifying symlink traversal protection.
"""
import asyncio
import os
from unittest.mock import patch

import pytest  # pylint: disable=import-error

# pylint: disable=import-error
from doxygen_mcp.utils import _update_ignore_file_sync
from doxygen_mcp.server import create_doxygen_project
# pylint: enable=import-error

def test_symlink_protection_gitignore(tmp_path):
    """
    Verify that update_ignore_file refuses to write to a symlink.
    """
    project_root = tmp_path
    target_file = project_root / "target.txt"
    target_file.write_text("sensitive data", encoding='utf-8')

    # Create symlink .gitignore -> target.txt
    symlink = project_root / ".gitignore"
    os.symlink(target_file, symlink)

    # Attempt to update ignore file
    # pylint: disable=protected-access
    result = _update_ignore_file_sync(project_root, "docs/")

    assert result is False, "Should return False when .gitignore is a symlink"
    assert target_file.read_text(encoding='utf-8') == "sensitive data", \
        "Should not modify target file"

def test_symlink_protection_doxyfile(tmp_path):
    """
    Verify that create_doxygen_project refuses to overwrite a symlinked Doxyfile.
    """
    async def run_test():
        project_root = tmp_path
        target_file = project_root / "target.txt"
        target_file.write_text("sensitive data", encoding='utf-8')

        # Create symlink Doxyfile -> target.txt
        symlink = project_root / "Doxyfile"
        os.symlink(target_file, symlink)

        # Mock dependencies
        with patch("doxygen_mcp.server.resolve_project_path", return_value=project_root):
            with patch("doxygen_mcp.server.update_ignore_file", return_value=True):
                with patch("doxygen_mcp.server.detect_primary_language", return_value="python"):
                    result = await create_doxygen_project("TestProject", str(project_root))

        assert "Security Error" in result, f"Should return security error, got: {result}"
        assert target_file.read_text(encoding='utf-8') == "sensitive data", \
            "Should not modify target file"

    # pylint: disable=no-member
    asyncio.run(run_test())

def test_overwrite_protection_doxyfile(tmp_path):
    """
    Verify that create_doxygen_project refuses to overwrite an existing Doxyfile.
    """
    async def run_test():
        project_root = tmp_path
        doxyfile = project_root / "Doxyfile"
        doxyfile.write_text("existing content", encoding='utf-8')

        # Mock dependencies
        with patch("doxygen_mcp.server.resolve_project_path", return_value=project_root):
            with patch("doxygen_mcp.server.update_ignore_file", return_value=True):
                with patch("doxygen_mcp.server.detect_primary_language", return_value="python"):
                    result = await create_doxygen_project("TestProject", str(project_root))

        assert "Doxyfile already exists" in result, f"Should return exists error, got: {result}"
        assert doxyfile.read_text(encoding='utf-8') == "existing content", \
            "Should not modify existing file"

    # pylint: disable=no-member
    asyncio.run(run_test())
