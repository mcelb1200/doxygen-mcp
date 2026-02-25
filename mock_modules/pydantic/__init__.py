"""
Mock implementation of pydantic for CI and tests.
"""

class BaseModel:
    """Mock BaseModel class."""
    def __init__(self, **kwargs):
        """Mock constructor."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def from_env(cls, **kwargs):
        """Mock from_env method."""
        return cls(**kwargs)
