import sys
from abc import abstractmethod
from contextvars import ContextVar
from typing import TextIO

from zrb.context.any_shared_context import AnySharedContext


class AnyContext(AnySharedContext):
    """`AnySharedContext` plus the per-task slice: retry attempt tracking,
    prefixed print/log output, and single-value template rendering."""

    @property
    @abstractmethod
    def attempt(self) -> int:
        """The current attempt number, 1 on the first try."""
        pass

    @abstractmethod
    def set_attempt(self, attempt: int):
        """Set the current attempt number."""
        pass

    @abstractmethod
    def set_max_attempt(self, max_attempt: int):
        """Set the number of attempts allowed before the task gives up."""
        pass

    @abstractmethod
    def update_task_env(self, task_env: dict[str, str]):
        """Merge `task_env` into this context's environment variables.

        Args:
            task_env: Variables to add or overwrite, by name.
        """

    @abstractmethod
    def print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
        plain: bool = False,
    ):
        """Print *values*, prefixed with this task's name and icon unless
        *plain*. Signature mirrors the builtin `print`; see `Context.print`
        for the concrete implementation."""
        pass

    @abstractmethod
    def print_err(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
        plain: bool = False,
    ):
        """Alias for `print`, for a caller that wants to name its output as
        error/diagnostic without changing where it goes."""
        pass

    @abstractmethod
    def log_debug(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        """Log *values* at `logging.DEBUG`, suppressed above that level."""
        pass

    @abstractmethod
    def log_info(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        """`log_debug`'s counterpart at `logging.INFO`."""
        pass

    @abstractmethod
    def log_warning(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        """`log_debug`'s counterpart at `logging.WARNING`."""
        pass

    @abstractmethod
    def log_error(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        """`log_debug`'s counterpart at `logging.ERROR`."""
        pass

    @abstractmethod
    def log_critical(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        """`log_debug`'s counterpart at `logging.CRITICAL`."""
        pass

    @abstractmethod
    def render_bool(self, template: str | bool) -> bool:
        """`render` a string template and parse it as a bool; a non-string
        value passes through unchanged."""
        pass

    @abstractmethod
    def render_int(self, template: str | int) -> int:
        """`render_bool`'s counterpart, parsed as an int."""
        pass

    @abstractmethod
    def render_float(self, template: str | float) -> float:
        """`render_bool`'s counterpart, parsed as a float."""
        pass


current_ctx: ContextVar[AnyContext | None] = ContextVar("current_ctx", default=None)


def get_current_ctx() -> AnyContext:
    ctx = current_ctx.get()
    if ctx is None:
        raise RuntimeError(
            "No active Zrb Context found. Are you running inside a task?"
        )
    return ctx


def zrb_print(
    *values: object,
    sep: str | None = " ",
    end: str | None = "\n",
    file: TextIO | None = sys.stderr,
    flush: bool = True,
    plain: bool = False,
):
    ctx = current_ctx.get()
    if ctx is not None:
        ctx.print(*values, sep=sep, end=end, file=file, flush=flush, plain=plain)
        return
    print(*values, sep=sep, end=end, file=file, flush=flush)
