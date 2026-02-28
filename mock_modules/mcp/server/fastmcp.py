"""
Mock implementation of FastMCP for CI and tests.
"""

class FastMCP:
    """Mock FastMCP class."""
    def __init__(self, name, *args, **kwargs): # pylint: disable=unused-argument
        """Mock constructor."""
        self.name = name
        self.tools = {}

    def tool(self, *args, **kwargs): # pylint: disable=unused-argument
        """Mock tool decorator."""
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator

    def run(self, *args, **kwargs): # pylint: disable=unused-argument
        """Mock run method."""
        pass
