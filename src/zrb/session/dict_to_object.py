from typing import Any
from collections.abc import Mapping


class DictToObject:
    def __init__(self, dictionary: Mapping[str, Any]):
        self._dictionary = dictionary
        for key, value in dictionary.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self._dictionary[key]

    def __setitem__(self, key, value):
        self._dictionary[key] = value
        setattr(self, key, value)

    def __getattr__(self, key):
        try:
            return self._dictionary[key]
        except KeyError:
            raise AttributeError(f"'DictToObject' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        if key == '_dictionary':
            super().__setattr__(key, value)
        else:
            self._dictionary[key] = value
            super().__setattr__(key, value)

    def __delattr__(self, key):
        if key in self._dictionary:
            del self._dictionary[key]
            super().__delattr__(key)
        else:
            raise AttributeError(f"'DictToObject' object has no attribute '{key}'")

    def __delitem__(self, key):
        del self._dictionary[key]
        delattr(self, key)

    def __contains__(self, key):
        return key in self._dictionary

    def update(self, other):
        self._dictionary.update(other)
        for key, value in other.items():
            setattr(self, key, value)

    def items(self):
        return self._dictionary.items()

    def keys(self):
        return self._dictionary.keys()

    def values(self):
        return self._dictionary.values()

    def get(self, key, default=None):
        return self._dictionary.get(key, default)

    def pop(self, key, default=None):
        value = self._dictionary.pop(key, default)
        if hasattr(self, key):
            delattr(self, key)
        return value

    def popitem(self):
        key, value = self._dictionary.popitem()
        delattr(self, key)
        return key, value

    def clear(self):
        self._dictionary.clear()
        for key in list(self.__dict__.keys()):
            if key != '_dictionary':
                delattr(self, key)

    def setdefault(self, key, default=None):
        value = self._dictionary.setdefault(key, default)
        setattr(self, key, value)
        return value 

    def __len__(self):
        return len(self._dictionary)

    def __repr__(self):
        return f"DictToObject({self._dictionary})"

    def __str__(self):
        return str(self._dictionary)

    def __iter__(self):
        return iter(self._dictionary)

    def copy(self):
        return DictToObject(self._dictionary.copy())

    def __eq__(self, other):
        if isinstance(other, dict):
            return self._dictionary == other
        if isinstance(other, DictToObject):
            return self._dictionary == other._dictionary
        return False
