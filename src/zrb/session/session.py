from typing import Any
from collections.abc import Mapping
import os
import datetime


class TaskStatus():
    def __init__(self):
        self._started: bool = False
        self._completed: bool = False

    def __repr__(self):
        return f"<TaskStatus started={self._started} completed={self._completed}>"

    def start(self):
        self._started = True

    def complete(self):
        self._completed = True

    def is_started(self):
        return self._started

    def is_completed(self):
        return self._completed


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

    def render(self, value: str):
        return value.format(
            input=self._inputs,
            args=self._args,
            envs=self._envs,
            xcoms=self._xcoms,
            os=os,
            datetime=datetime
        )
