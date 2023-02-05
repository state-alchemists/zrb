from typing import Any


class DynamicModel:
    def __init__(self, **kwargs: Any):
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        return str(self.__dict__)

    def __getattribute__(self, name):
        '''
        Return None if attribute not found
        '''
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return None
