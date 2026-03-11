"""
Doxygen MCP Server

A comprehensive Model Context Protocol server that provides full access to Doxygen's
documentation generation capabilities. This server exposes Doxygen's complete feature
set through a clean MCP interface, enabling AI assistants to generate, configure,
and manage documentation for any supported programming language.

Supported Languages:
- Primary: C, C++, Python, PHP
- Extended: Java, C#, JavaScript, Objective-C, Fortran, VHDL
- Additional: Batch, PowerShell, Bash, Perl, Go (through extension mapping)

Key Features:
- Project initialization and configuration management
- Multi-format output generation (HTML, PDF, LaTeX, XML, etc.)
- Advanced diagram generation (UML, call graphs, inheritance diagrams)
- Documentation coverage analysis and validation
- Cross-referencing and link generation
- Custom theme and layout support
"""

__version__ = "1.0.0"
__author__ = "Positronikal"
__email__ = "hoyt.harness@gmail.com"

try:
    from .server import main
    __all__ = ["main"]
except (ImportError, ModuleNotFoundError):
    # Allow importing the package even if dependencies aren't met
    # (e.g. for basic utility access in scripts)
    __all__ = []
