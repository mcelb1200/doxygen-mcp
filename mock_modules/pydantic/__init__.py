"""
Mock Pydantic for testing
"""

# pylint: disable=too-few-public-methods

class BaseModel:
    """Mock BaseModel class"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    @classmethod
    def from_env(cls, **kwargs):
        """Mock from_env method"""
        return cls(**kwargs)
