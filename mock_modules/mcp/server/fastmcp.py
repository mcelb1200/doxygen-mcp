"""
Mock module for Pylint.
"""
class FastMCP:
    def __init__(self, *args, **kwargs):
        pass
    def tool(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator
    def run(self, *args, **kwargs):
        pass
