import sys
from abc import abstractmethod
from typing import TextIO

from zrb.context.any_shared_context import AnySharedContext


class AnyContext(AnySharedContext):
    """Abstract base class for managing task contexts, logging, and rendering.

    This class provides methods for managing context-specific data such as
    attempt counts, logging, and rendering templates with additional data.
    Subclasses must implement all abstract methods.
    """

    @abstractmethod
    def set_attempt(self, attempt: int):
        """Sets the current attempt count.

        Args:
            attempt (int): The current attempt count.
        """
        pass

    @abstractmethod
    def set_max_attempt(self, max_attempt: int):
        """Sets the maximum number of attempts.

        Args:
            max_attempt (int): The maximum number of attempts allowed.
        """
        pass

    @abstractmethod
    def update_task_env(self, task_env: dict[str, str]):
        pass

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
        """Prints values to the specified output stream.

        Args:
            *values (object): The values to be printed.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to print to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
            plain (bool, optional): Whether to use plain text. Defaults to False.
        """
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
        """Logs debug-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
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
        """Logs info-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
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
        """Logs warning-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
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
        """Logs error-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
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
        """Logs critical-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
        pass

    @abstractmethod
    def render_bool(self, template: str | bool) -> bool:
        """Renders a template string into boolean.

        Args:
            template (str | bool): The template string to be rendered or the value.

        Returns:
            bool: The rendered template as a boolean.
        """
        pass

    @abstractmethod
    def render_int(self, template: str | int) -> int:
        """Renders a template string into integer.

        Args:
            template (str | int): The template string to be rendered or the value.

        Returns:
            int: The rendered template as a integer.
        """
        pass

    @abstractmethod
    def render_float(self, template: str | float) -> float:
        """Renders a template string into float.

        Args:
            template (str | float): The template string to be rendered or the value.

        Returns:
            float: The rendered template as a float.
        """
        pass
