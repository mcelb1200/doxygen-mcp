"""
Tests for verifying symlink traversal protection.
"""
# pylint: disable=import-error, redefined-outer-name
import asyncio
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from doxygen_mcp.utils import _update_ignore_file_sync
from doxygen_mcp.server import create_doxygen_project

def test_symlink_protection_gitignore(tmp_path):
    """Verify that update_ignore_file refuses to write to a symlink."""
    project_root = tmp_path
    target_file = project_root / "target.txt"
    target_file.write_text("sensitive data", encoding='utf-8')

    # Create symlink .gitignore -> target.txt
    symlink = project_root / ".gitignore"
    os.symlink(target_file, symlink)

    # Attempt to update ignore file
    result = _update_ignore_file_sync(project_root, "docs/")

    assert result is False
    assert target_file.read_text(encoding='utf-8') == "sensitive data"

@pytest.mark.asyncio
async def test_symlink_protection_doxyfile(tmp_path):
    """Verify that create_doxygen_project refuses to overwrite a symlinked Doxyfile."""
    project_root = tmp_path
    target_file = project_root / "target.txt"
    target_file.write_text("sensitive data", encoding='utf-8')

    # Create symlink Doxyfile -> target.txt
    symlink = project_root / "Doxyfile"
    os.symlink(target_file, symlink)

    # Mock dependencies
    with patch("doxygen_mcp.server.resolve_project_path", return_value=project_root), \
         patch("doxygen_mcp.server.update_ignore_file", new_callable=AsyncMock, return_value=True), \
         patch("doxygen_mcp.server.detect_primary_language", new_callable=AsyncMock, return_value="python"):

        result = await create_doxygen_project("TestProject", str(project_root))

    assert "Security Error" in result
    assert target_file.read_text(encoding='utf-8') == "sensitive data"

@pytest.mark.asyncio
async def test_overwrite_protection_doxyfile(tmp_path):
    """Verify that create_doxygen_project refuses to overwrite an existing Doxyfile."""
    project_root = tmp_path
    doxyfile = project_root / "Doxyfile"
    doxyfile.write_text("existing content", encoding='utf-8')

    # Mock dependencies
    with patch("doxygen_mcp.server.resolve_project_path", return_value=project_root), \
         patch("doxygen_mcp.server.update_ignore_file", new_callable=AsyncMock, return_value=True), \
         patch("doxygen_mcp.server.detect_primary_language", new_callable=AsyncMock, return_value="python"):

        result = await create_doxygen_project("TestProject", str(project_root))

    assert "already exists" in result
    assert doxyfile.read_text(encoding='utf-8') == "existing content"
