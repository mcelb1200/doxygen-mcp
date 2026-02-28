"""
Mock module for Pylint.
"""

class BaseModel:
    """Mock BaseModel class."""
    def __init__(self, **data):
        for key, value in data.items():
            setattr(self, key, value)

    def model_dump(self):
        """Mock model_dump method."""
        return self.__dict__
