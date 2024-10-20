from typing import Any
from collections.abc import Mapping
import os
import datetime


class DictToObject:
    def __init__(self, dictionary):
        self._dictionary = dictionary
        for key, value in dictionary.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self._dictionary[key]


def fstring_like_format(template: str, data: Mapping[str, Any]):
    # Safely evaluate the template as a Python expression
    return eval(f'f"""{template}"""', {}, data)


class Session():
    def __init__(
        self,
        inputs: Mapping[str, Any] = {},
        args: list[Any] = [],
        envs: Mapping[str, str] = {},
        xcoms: Mapping[str, list[Any]] = {}
    ):
        self.inputs = inputs
        self.args = args
        self.envs = envs
        self.xcoms = xcoms

    def __repr__(self):
        inputs = self.inputs
        args = self.args
        envs = self.envs
        xcoms = self.xcoms
        return f"<Session inputs={inputs} args={args} envs={envs} xcoms={xcoms}>"

    def render(self, template: str, additional_data: Mapping[str, Any] = {}):
        return fstring_like_format(
            template=template,
            data={
                "input": DictToObject(self.inputs),
                "args": self.args,
                "env": DictToObject(self.envs),
                "xcom": DictToObject(self.xcoms),
                "os": os,
                "datetime": datetime,
                **additional_data,
            }
        )
