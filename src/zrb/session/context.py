from typing import Any, TextIO
from collections.abc import Mapping
from .any_context import AnyContext
from .shared_context import SharedContext
from ..config import SHOW_TIME
from ..util.cli.style import stylize

import datetime
import sys


class Context(AnyContext):
    def __init__(
        self,
        shared_context: SharedContext,
        task_name: str,
        color: int,
        icon: str
    ):
        self._shared_context = shared_context
        self.inputs = shared_context.inputs
        self.args = shared_context.args
        self.envs = shared_context.envs
        self.xcoms = shared_context.xcoms
        self._task_name = task_name
        self._color = color
        self._icon = icon
        self._attempt = 0
        self._max_attempt = 0

    def __repr__(self):
        class_name = self.__class__.__name__
        inputs = self.inputs
        args = self.args
        envs = self.envs
        xcoms = self.xcoms
        return f"<{class_name} inputs={inputs} args={args} envs={envs} xcoms={xcoms}>"

    def set_attempt(self, attempt: int):
        self._attempt = attempt

    def set_max_attempt(self, max_attempt: int):
        self._max_attempt = max_attempt

    def render(self, template: str, additional_data: Mapping[str, Any] = {}):
        return self._shared_context.render(
            template=template, additional_data=additional_data
        )

    def print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        color = self._color
        icon = self._icon
        task_name = self._task_name
        padded_task_name = task_name.ljust(20)
        attempt_status = f"{self._attempt}/{self._max_attempt}"
        if SHOW_TIME:
            now = datetime.datetime.now()
            formatted_time = now.strftime("%Y-%m-%d %H:%M:%S.%f")
            prefix = stylize(
                f"{formatted_time} {attempt_status} {icon} {padded_task_name}",
                color=color
            )
        else:
            prefix = stylize(f"{attempt_status} {icon} {padded_task_name}", color=color)
        message = sep.join([f"{value}" for value in values])
        print(f"{prefix} {message}", sep=sep, end=end, file=file, flush=flush)
