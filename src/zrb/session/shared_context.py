from typing import Any
from collections import deque
from collections.abc import Mapping
from .any_shared_context import AnySharedContext

import datetime
import os


class DictToObject:
    def __init__(self, dictionary):
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


def fstring_like_format(template: str, data: Mapping[str, Any]) -> str:
    # Safely evaluate the template as a Python expression
    try:
        return eval(f'f"""{template}"""', {}, data)
    except Exception:
        raise ValueError(f"Failed to parse template: {template}")


class SharedContext(AnySharedContext):
    def __init__(
        self,
        input: Mapping[str, Any] = {},
        args: list[Any] = [],
        env: Mapping[str, str] = {},
        xcom: Mapping[str, deque] = {}
    ):
        self.input = DictToObject(input)
        self.args = args
        self.env = DictToObject(env)
        self.xcom = DictToObject(xcom)

    def __repr__(self):
        class_name = self.__class__.__name__
        input = self.input
        args = self.args
        env = self.env
        xcom = self.xcom
        return f"<{class_name} input={input} arg={args} env={env} xcom={xcom}>"

    def render(self, template: str, additional_data: Mapping[str, Any] = {}) -> str:
        return fstring_like_format(
            template=template,
            data={
                "input": self.input,
                "args": self.args,
                "env": self.env,
                "xcom": self.xcom,
                "os": os,
                "datetime": datetime,
                **additional_data,
            }
        )
