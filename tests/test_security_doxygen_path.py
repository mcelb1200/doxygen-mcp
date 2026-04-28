
import os
import sys
import shutil
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest # pylint: disable=import-error

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# pylint: disable=import-error
from doxygen_mcp.utils import get_doxygen_executable
from doxygen_mcp.server import check_doxygen_install
import doxygen_mcp.server
# pylint: enable=import-error

@pytest.fixture(autouse=True)
def clear_doxygen_cache():
    """Clear Doxygen version cache before each test"""
    doxygen_mcp.server._DOXYGEN_VERSION_CACHE.clear()
    yield

@pytest.mark.asyncio
async def test_get_doxygen_executable_valid():
    """Test get_doxygen_executable with a valid mock doxygen"""
    with tempfile.TemporaryDirectory() as temp_dir:
        doxygen_bin = Path(temp_dir) / "doxygen"
        doxygen_bin.touch(mode=0o755)

        # Add temp_dir to PATH
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{temp_dir}{os.pathsep}{old_path}"

        try:
            with patch.dict(os.environ, {"DOXYGEN_PATH": "doxygen"}):
                exe = get_doxygen_executable()
                assert Path(exe).name == "doxygen"
                assert Path(exe).is_absolute()
        finally:
            os.environ["PATH"] = old_path

@pytest.mark.asyncio
async def test_get_doxygen_executable_invalid_name():
    """Test get_doxygen_executable with an invalid executable name"""
    with tempfile.TemporaryDirectory() as temp_dir:
        malicious_bin = Path(temp_dir) / "not_doxygen"
        malicious_bin.touch(mode=0o755)

        with patch.dict(os.environ, {"DOXYGEN_PATH": str(malicious_bin)}):
            with pytest.raises(ValueError, match="Security Error: Invalid Doxygen executable name"):
                get_doxygen_executable()

@pytest.mark.asyncio
async def test_get_doxygen_executable_shutil_which_invalid():
    """Test get_doxygen_executable by mocking shutil.which to return an invalid executable"""
    with patch("doxygen_mcp.utils.shutil.which", return_value="/usr/bin/bash"):
        with patch.dict(os.environ, {"DOXYGEN_PATH": "bash"}):
            with pytest.raises(ValueError, match="Security Error: Invalid Doxygen executable name 'bash'"):
                get_doxygen_executable()

@pytest.mark.asyncio
async def test_get_doxygen_executable_not_found():
    """Test get_doxygen_executable when the executable is not found"""
    with patch.dict(os.environ, {"DOXYGEN_PATH": "/nonexistent/path/to/doxygen"}):
        with pytest.raises(ValueError, match="Doxygen executable not found"):
            get_doxygen_executable()

@pytest.mark.asyncio
@patch('asyncio.create_subprocess_exec')
async def test_check_doxygen_install_invalid_version(mock_exec):
    """Test check_doxygen_install with an unexpected version format"""
    # Create a mock process
    process = MagicMock()
    # Malicious output that doesn't look like a version number
    process.communicate = AsyncMock(return_value=(b"Malicious output\n", b""))
    process.returncode = 0

    mock_exec.return_value = process

    # We need to mock get_doxygen_executable to return a "valid" path
    # so it passes the name check
    with patch('doxygen_mcp.server.get_doxygen_executable', return_value="/usr/bin/doxygen"):
        result = await check_doxygen_install()
        assert "[ERROR] Unexpected Doxygen version format" in result

@pytest.mark.asyncio
@patch('asyncio.create_subprocess_exec')
async def test_check_doxygen_install_valid_version(mock_exec):
    """Test check_doxygen_install with a valid version format"""
    process = MagicMock()
    process.communicate = AsyncMock(return_value=(b"1.9.4\n", b""))
    process.returncode = 0
    mock_exec.return_value = process

    with patch('doxygen_mcp.server.get_doxygen_executable', return_value="/usr/bin/doxygen"):
        result = await check_doxygen_install()
        assert "[SUCCESS] Doxygen 1.9.4 is installed and working" in result
