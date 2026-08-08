from abc import ABC, abstractmethod
from collections.abc import Callable

from zrb.attr.type import StrAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_str_attr
from zrb.util.file import read_file


class AnyCmdVal(ABC):
    """A shell command resolved against a task context at run time."""

    @abstractmethod
    def to_str(self, ctx: AnyContext) -> str:
        """Resolve this value into the command string to execute."""


class CmdPath(AnyCmdVal):
    def __init__(self, path: StrAttr, auto_render: bool = True):
        """Read the command to run from a file.

        Args:
            path: Path to the script file. An f-string template rendered against
                the task context, or a callable taking it.
            auto_render: Whether to render `path` as a template.
        """
        self._path = path
        self._auto_render = auto_render

    def to_str(self, ctx: AnyContext) -> str:
        """Render the path, then return the contents of the file it names."""
        file_path = get_str_attr(ctx, self._path, "", self._auto_render)
        return read_file(file_path)


class Cmd(AnyCmdVal):
    def __init__(self, cmd: StrAttr, auto_render: bool = True):
        """Wrap a command string for deferred rendering.

        Args:
            cmd: The command. An f-string template rendered against the task
                context, or a callable taking it.
            auto_render: Whether to render `cmd` as a template. Set False to run a
                literal command containing braces.
        """
        self._cmd = cmd
        self._auto_render = auto_render

    def to_str(self, ctx: AnyContext) -> str:
        """Render the command template against `ctx`."""
        return get_str_attr(ctx, self._cmd, "", self._auto_render)


SingleCmdVal = AnyCmdVal | fstring | Callable[[AnyContext], str]
CmdVal = SingleCmdVal | list[SingleCmdVal]
