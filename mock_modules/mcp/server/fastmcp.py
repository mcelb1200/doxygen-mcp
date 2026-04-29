"""
Mock implementation of FastMCP for CI and tests.
"""

class FastMCP:
    """Mock FastMCP class."""
    def __init__(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Mock constructor."""

    def tool(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Mock tool decorator."""
        def decorator(func):
            """Mock decorator."""
            return func
        return decorator

    def run(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Mock run method."""
