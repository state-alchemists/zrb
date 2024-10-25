from typing import Any, TextIO
from collections.abc import Mapping
from .any_context import AnyContext
from .shared_context import SharedContext
from ..util.cli.style import stylize, stylize_error, stylize_log, stylize_warning

import datetime
import logging
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
        self.input = shared_context.input
        self.args = shared_context.args
        self.env = shared_context.env
        self.xcom = shared_context.xcom
        self._task_name = task_name
        self._color = color
        self._icon = icon
        self._attempt = 0
        self._max_attempt = 0

    def __repr__(self):
        class_name = self.__class__.__name__
        input = self.input
        args = self.args
        env = self.env
        xcom = self.xcom
        return f"<{class_name} input={input} arg={args} env={env} xcom={xcom}>"

    def set_attempt(self, attempt: int):
        self._attempt = attempt

    def set_max_attempt(self, max_attempt: int):
        self._max_attempt = max_attempt

    def render(self, template: str, additional_data: Mapping[str, Any] = {}) -> str:
        return self._shared_context.render(
            template=template, additional_data=additional_data
        )

    def render_bool(self, template: str, additional_data: Mapping[str, Any] = {}) -> bool:
        return self._shared_context.render_bool(
            template=template, additional_data=additional_data
        )

    def render_int(self, template: str, additional_data: Mapping[str, Any] = {}) -> int:
        return self._shared_context.render_int(
            template=template, additional_data=additional_data
        )

    def render_float(self, template: str, additional_data: Mapping[str, Any] = {}) -> float:
        return self._shared_context.render_float(
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
        if self._shared_context.show_time():
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
        if self._shared_context.get_logging_level() <= logging.DEBUG:
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
        if self._shared_context.get_logging_level() <= logging.INFO:
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
        if self._shared_context.get_logging_level() <= logging.INFO:
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
        if self._shared_context.get_logging_level() <= logging.ERROR:
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
        if self._shared_context.get_logging_level() <= logging.CRITICAL:
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_error(f"[CRITICAL] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)
