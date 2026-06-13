import runpy
from unittest.mock import patch


def test_main_execution():
    with patch("doxygen_mcp.server.main") as mock_main:
        runpy.run_module("doxygen_mcp.__main__", run_name="__main__")
        mock_main.assert_called_once()
