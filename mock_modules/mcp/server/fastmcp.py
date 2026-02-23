"""
Mock FastMCP for testing
"""

# pylint: disable=unused-argument

class FastMCP:
    """Mock FastMCP class"""
    def __init__(self, *args, **kwargs):
        pass
    def tool(self, *args, **kwargs):
        """Mock tool decorator"""
        def decorator(f):
            return f
        return decorator
    def run(self, *args, **kwargs):
        """Mock run method"""
        pass
