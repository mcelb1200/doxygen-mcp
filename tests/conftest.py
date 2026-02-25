import sys
import asyncio
import pytest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """
    Run asyncio marked tests (or async functions) in an event loop.
    """
    if asyncio.iscoroutinefunction(pyfuncitem.obj):
        funcargs = pyfuncitem.funcargs
        testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
        asyncio.run(pyfuncitem.obj(**testargs))
        return True
    return None

# Mock defusedxml if not installed
try:
    import defusedxml.ElementTree
except ImportError:
    mock_defusedxml = MagicMock()
    mock_defusedxml.ElementTree = ET
    sys.modules["defusedxml"] = mock_defusedxml
    sys.modules["defusedxml.ElementTree"] = ET

# Mock mcp if not installed
try:
    import mcp.server.fastmcp
except ImportError:
    mock_mcp = MagicMock()
    mock_server = MagicMock()
    mock_fastmcp = MagicMock()

    class FastMCP:
        def __init__(self, name, *args, **kwargs):
            self.name = name
            self.tools = {}

        def tool(self):
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator

        def run(self):
            pass

    mock_fastmcp.FastMCP = FastMCP
    mock_server.fastmcp = mock_fastmcp
    mock_mcp.server = mock_server

    sys.modules["mcp"] = mock_mcp
    sys.modules["mcp.server"] = mock_server
    sys.modules["mcp.server.fastmcp"] = mock_fastmcp
