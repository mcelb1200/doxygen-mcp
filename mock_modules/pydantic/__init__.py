class BaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    @classmethod
    def from_env(cls, **kwargs):
        return cls(**kwargs)
