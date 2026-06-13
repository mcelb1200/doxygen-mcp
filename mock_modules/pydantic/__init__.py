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

    def model_dump(self):
        """Mock model_dump method."""
        return self.__dict__.copy()

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
