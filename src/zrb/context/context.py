from typing import Any, TextIO
from .any_context import AnyContext
from .any_shared_context import AnySharedContext
from ..dict_to_object.dict_to_object import DictToObject
from ..util.cli.style import stylize, stylize_error, stylize_log, stylize_warning
from ..util.string.conversion import to_boolean

import datetime
import logging
import sys


class Context(AnyContext):
    def __init__(
        self,
        shared_context: AnySharedContext,
        task_name: str,
        color: int,
        icon: str
    ):
        self._shared_ctx = shared_context
        self._task_name = task_name
        self._color = color
        self._icon = icon
        self._attempt = 0
        self._max_attempt = 0

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} shared_ctx={self._shared_ctx}>"

    @property
    def input(self) -> DictToObject:
        return self._shared_ctx.input

    @property
    def env(self) -> DictToObject:
        return self._shared_ctx.env

    @property
    def args(self) -> list[Any]:
        return self._shared_ctx.args

    @property
    def xcom(self) -> DictToObject:
        return self._shared_ctx.xcom

    def set_attempt(self, attempt: int):
        self._attempt = attempt

    def set_max_attempt(self, max_attempt: int):
        self._max_attempt = max_attempt

    def get_logging_level(self) -> int:
        return self._shared_ctx.get_logging_level()

    def should_show_time(self) -> bool:
        return self._shared_ctx.should_show_time()

    def render(self, template: str) -> str:
        return self._shared_ctx.render(template=template)

    def render_bool(self, template: str | bool) -> bool:
        if isinstance(template, bool):
            return template
        return to_boolean(self.render(template))

    def render_int(self, template: str | int) -> int:
        if isinstance(template, int):
            return template
        return int(self.render(template))

    def render_float(self, template: str) -> float:
        if isinstance(template, float):
            return template
        return float(self.render(template))

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
        if self._attempt == 0:
            attempt_status = "".ljust(5)
        else:
            attempt_status = f"{self._attempt}/{self._max_attempt}".ljust(5)
        if self._shared_ctx.should_show_time():
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

    def log_debug(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        if self._shared_ctx.get_logging_level() <= logging.DEBUG:
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_log(f"[DEBUG] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_info(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        if self._shared_ctx.get_logging_level() <= logging.INFO:
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_log(f"[INFO] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_warning(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        if self._shared_ctx.get_logging_level() <= logging.INFO:
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_warning(f"[WARNING] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_error(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        if self._shared_ctx.get_logging_level() <= logging.ERROR:
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_error(f"[ERROR] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_critical(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        if self._shared_ctx.get_logging_level() <= logging.CRITICAL:
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_error(f"[CRITICAL] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)
