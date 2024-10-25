from typing import Any
from collections.abc import Mapping


class DictToObject:
    def __init__(self, dictionary: Mapping[str, Any]):
        self.__dictionary = dictionary
        for key, value in dictionary.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self.__dictionary[key]

    def __setitem__(self, key, value):
        self.__dictionary[key] = value
        setattr(self, key, value)

    def __getattr__(self, key):
        try:
            return self.__dictionary[key]
        except KeyError:
            raise AttributeError(f"'DictToObject' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        if key == '_DictToObject__dictionary':
            super().__setattr__(key, value)
        else:
            self.__dictionary[key] = value
            super().__setattr__(key, value)

    def __delattr__(self, key):
        if key in self.__dictionary:
            del self.__dictionary[key]
            super().__delattr__(key)
        else:
            raise AttributeError(f"'DictToObject' object has no attribute '{key}'")

    def __delitem__(self, key):
        del self.__dictionary[key]
        delattr(self, key)

    def __contains__(self, key):
        return key in self.__dictionary

    def update(self, other):
        self.__dictionary.update(other)
        for key, value in other.items():
            setattr(self, key, value)

    def items(self):
        return self.__dictionary.items()

    def keys(self):
        return self.__dictionary.keys()

    def values(self):
        return self.__dictionary.values()

    def get(self, key, default=None):
        return self.__dictionary.get(key, default)

    def pop(self, key, default=None):
        value = self.__dictionary.pop(key, default)
        if hasattr(self, key):
            delattr(self, key)
        return value

    def popitem(self):
        key, value = self.__dictionary.popitem()
        delattr(self, key)
        return key, value

    def clear(self):
        self.__dictionary.clear()
        for key in list(self.__dict__.keys()):
            if key != '_DictToObject__dictionary':
                delattr(self, key)

    def setdefault(self, key, default=None):
        value = self.__dictionary.setdefault(key, default)
        setattr(self, key, value)
        return value 

    def __len__(self):
        return len(self.__dictionary)

    def __repr__(self):
        return f"DictToObject({self.__dictionary})"

    def __str__(self):
        return str(self.__dictionary)

    def __iter__(self):
        return iter(self.__dictionary)

    def copy(self):
        return DictToObject(self.__dictionary.copy())

    def __eq__(self, other):
        if isinstance(other, dict):
            return self.__dictionary == other
        if isinstance(other, DictToObject):
            return self.__dictionary == other.__dictionary
        return False
