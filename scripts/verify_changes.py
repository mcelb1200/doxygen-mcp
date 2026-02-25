"""
Script to verify changes to the Doxygen MCP server.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# pylint: disable=import-error
from doxygen_mcp.server import create_doxygen_project
from doxygen_mcp.utils import resolve_project_path
# pylint: enable=import-error

def test_resolve_logic():
    """Test the path resolution logic."""
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
    if "DOXYGEN_PROJECT_ROOT" in os.environ:
        del os.environ["DOXYGEN_PROJECT_ROOT"]
    try:
        # Should resolve to safe roots or raise if none allowed/found
        resolve_project_path(None)
        print("  Missing path: OK (resolved to default)")
    except ValueError:
        print("  Missing path: OK (raised error as expected)")

async def test_tools():
    """Test the core tools functionality."""
    print("\nTesting tools...")

    # Setup
    test_dir = Path("test_verify_env").resolve()
    if test_dir.exists():
        import shutil  # pylint: disable=import-outside-toplevel
        shutil.rmtree(test_dir)

    os.environ["DOXYGEN_PROJECT_ROOT"] = str(test_dir)

    # Test create_doxygen_project with implicit path
    print("  Running create_doxygen_project(project_path=None)...")
    try:
        result = await create_doxygen_project(
            project_name="Verify Project",
            # project_path defaults to None
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

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"  Exception during tool call: {e}")


    # Clean up
    import shutil  # pylint: disable=import-outside-toplevel
    if test_dir.exists():
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_resolve_logic()
    asyncio.run(test_tools())
