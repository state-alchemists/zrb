import datetime
import logging
import sys
from typing import Any, TextIO

from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.dot_dict.dot_dict import DotDict
from zrb.session.any_session import AnySession
from zrb.util.cli.style import (
    remove_style,
    stylize,
    stylize_error,
    stylize_log,
    stylize_warning,
)
from zrb.util.string.conversion import to_boolean


class Context(AnyContext):
    def __init__(
        self, shared_ctx: AnySharedContext, task_name: str, color: int, icon: str
    ):
        self._shared_ctx = shared_ctx
        self._env = shared_ctx.env.copy()
        self._task_name = task_name
        self._color = color
        self._icon = icon
        self._attempt = 0
        self._max_attempt = 0

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} shared_ctx={self._shared_ctx}>"

    @property
    def input(self) -> DotDict:
        return self._shared_ctx.input

    @property
    def env(self) -> DotDict:
        return self._env

    @property
    def args(self) -> list[Any]:
        return self._shared_ctx.args

    @property
    def xcom(self) -> DotDict:
        return self._shared_ctx.xcom

    @property
    def shared_log(self) -> list[str]:
        return self._shared_ctx.shared_log

    @property
    def session(self) -> AnySession | None:
        return self._shared_ctx._session

    def update_task_env(self, task_env: dict[str, str]):
        self._env.update(task_env)

    def append_to_shared_log(self, message: str):
        self._shared_ctx.append_to_shared_log(message)

    def set_session(self, session: AnySession):
        self._shared_ctx.set_session(session)

    def set_attempt(self, attempt: int):
        self._attempt = attempt

    def set_max_attempt(self, max_attempt: int):
        self._max_attempt = max_attempt

    def get_logging_level(self) -> int:
        return self._shared_ctx.get_logging_level()

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

    def render_float(self, template: str | float) -> float:
        if isinstance(template, float) or isinstance(template, int):
            return template
        return float(self.render(template))

    def print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
        plain: bool = False,
    ):
        sep = " " if sep is None else sep
        message = sep.join([f"{value}" for value in values])
        if plain:
            # self.append_to_shared_log(remove_style(message))
            print(message, sep=sep, end=end, file=file, flush=flush)
            self.append_to_shared_log(remove_style(f"{message}{end}"))
            return
        color = self._color
        icon = self._icon
        max_name_length = max(len(name) + len(icon) for name in self.session.task_names)
        styled_task_name = f"{icon} {self._task_name}"
        padded_styled_task_name = styled_task_name.rjust(max_name_length + 1)
        if self._attempt == 0:
            attempt_status = "".ljust(5)
        else:
            attempt_status = f"{self._attempt}/{self._max_attempt}".ljust(5)
        now = datetime.datetime.now()
        formatted_time = now.strftime("%y%m%d %H:%M:%S.%f")[:19] + " "
        prefix = f"{formatted_time}{attempt_status} {padded_styled_task_name} ⬤ "
        self.append_to_shared_log(remove_style(f"{prefix} {message}{end}"))
        stylized_prefix = stylize(prefix, color=color)
        print(f"{stylized_prefix} {message}", sep=sep, end=end, file=file, flush=flush)

    def log_debug(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        if self._shared_ctx.get_logging_level() <= logging.DEBUG:
            sep = " " if sep is None else sep
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_log(f"[DEBUG] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_info(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        if self._shared_ctx.get_logging_level() <= logging.INFO:
            sep = " " if sep is None else sep
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_log(f"[INFO] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_warning(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        if self._shared_ctx.get_logging_level() <= logging.INFO:
            sep = " " if sep is None else sep
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_warning(f"[WARNING] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_error(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        if self._shared_ctx.get_logging_level() <= logging.ERROR:
            sep = " " if sep is None else sep
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_error(f"[ERROR] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)

    def log_critical(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        if self._shared_ctx.get_logging_level() <= logging.CRITICAL:
            sep = " " if sep is None else sep
            message = sep.join([f"{value}" for value in values])
            stylized_message = stylize_error(f"[CRITICAL] {message}")
            self.print(stylized_message, sep=sep, end=end, file=file, flush=flush)
