"""
Tests for Doxygen MCP Server - Symlink handling.
"""
import asyncio
import tempfile
from pathlib import Path


# pylint: disable=import-error
from doxygen_mcp.server import create_doxygen_project
# pylint: enable=import-error

def run_async(coro):
    """Helper to run a coroutine synchronously."""
    return asyncio.run(coro)

def test_create_project_follow_symlinks():
    """Test creating a project with follow_symlinks=True."""
    async def _test():
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await create_doxygen_project(
                project_name="Test Symlinks",
                project_path=temp_dir,
                language="cpp",
                follow_symlinks=True
            )

            assert "✅ Doxygen project 'Test Symlinks' created successfully" in result

            doxyfile_path = Path(temp_dir) / "Doxyfile"
            assert doxyfile_path.exists()

            with open(doxyfile_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert "EXCLUDE_SYMLINKS       = NO" in content

    run_async(_test())

def test_create_project_default_no_symlinks():
    """Test creating a project with default settings (follow_symlinks=False)."""
    async def _test():
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await create_doxygen_project(
                project_name="Test Secure",
                project_path=temp_dir,
                language="cpp"
            )

            assert "✅ Doxygen project 'Test Secure' created successfully" in result

            doxyfile_path = Path(temp_dir) / "Doxyfile"
            assert doxyfile_path.exists()

            with open(doxyfile_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert "EXCLUDE_SYMLINKS       = YES" in content

    run_async(_test())
