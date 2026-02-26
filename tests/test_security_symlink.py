"""
Tests for verifying symlink traversal protection.
"""
# pylint: disable=import-error
import asyncio
import os
from pathlib import Path
from unittest.mock import patch

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
    # pylint: disable=protected-access
    result = _update_ignore_file_sync(project_root, "docs/")

    assert result is False
    assert target_file.read_text(encoding='utf-8') == "sensitive data"
