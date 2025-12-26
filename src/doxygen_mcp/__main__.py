"""
Main entry point for the Doxygen MCP server.

This module provides the command-line entry point for running the Doxygen MCP server.
It can be invoked using:
    - uv run doxygen-mcp
    - python -m doxygen_mcp
"""

from .server import main

if __name__ == "__main__":
    main()
