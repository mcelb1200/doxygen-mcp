import sys
import asyncio
import pytest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

# Mock defusedxml to use standard xml.etree.ElementTree
mock_defusedxml = MagicMock()
mock_defusedxml.ElementTree = ET
sys.modules["defusedxml"] = mock_defusedxml
sys.modules["defusedxml.ElementTree"] = ET

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
