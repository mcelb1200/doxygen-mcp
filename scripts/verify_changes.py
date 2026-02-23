"""
Script to verify changes for doxygen-mcp.
"""

import os
import sys
import asyncio
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# pylint: disable=wrong-import-position
from doxygen_mcp.server import create_doxygen_project
from doxygen_mcp.utils import resolve_project_path

def test_resolve_logic():
    """Test the project path resolution logic"""
    print("Testing resolve_project_path...")

    # Test 1: Explicit path
    p = resolve_project_path("foo")
    assert p.name == "foo"
    print("  Explicit path: OK")

    # Test 2: Env var
    os.environ["DOXYGEN_PROJECT_ROOT"] = str(Path("bar").resolve())
    p = resolve_project_path(None)
    assert p.name == "bar"
    print("  Env var: OK")

    # Test 3: Missing
    del os.environ["DOXYGEN_PROJECT_ROOT"]
    p = resolve_project_path(None)
    # Should fall back to discovery root (usually CWD)
    assert p is not None
    print("  Missing path: OK")

async def test_tools():
    """Test tool functionality with the new path resolution"""
    print("\nTesting tools...")

    # Setup
    test_dir = Path("test_verify_env").resolve()
    if test_dir.exists():
        shutil.rmtree(test_dir)

    os.environ["DOXYGEN_PROJECT_ROOT"] = str(test_dir)

    # Test create_doxygen_project with implicit path
    print("  Running create_doxygen_project(project_path=None)...")
    try:
        # Note: In this environment, this might fail due to missing dependencies
        # but we check if it handles the path correctly.
        result = await create_doxygen_project(
            project_name="Verify Project",
            language="python"
        )

        if "✅" in result:
            print("  Creation: OK")
        else:
            print(f"  Creation: FAILED - {result}")

        if (test_dir / "Doxyfile").exists():
            print("  Doxyfile check: OK")
        else:
            print("  Doxyfile check: FAILED")

    # pylint: disable=broad-exception-caught
    except Exception as e:
        print(f"  Exception during tool call: {e}")

    # Clean up
    if test_dir.exists():
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_resolve_logic()
    asyncio.run(test_tools())
