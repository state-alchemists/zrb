from collections.abc import Callable

from zrb.attr.type import StrAttr
from zrb.cmd.any_cmd_val import AnyCmdVal
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_str_attr
from zrb.util.file import read_file


class CmdPath(AnyCmdVal):
    def __init__(self, path: StrAttr):
        """Read the command to run from a file.

        Args:
            path: Path to the script file. A literal, a `Tpl` rendered
                against the task context, or a callable taking it.
        """
        self._path = path

    def to_str(self, ctx: AnyContext) -> str:
        """Resolve the path, then return the contents of the file it names."""
        file_path = get_str_attr(ctx, self._path, "")
        return read_file(file_path)


class Cmd(AnyCmdVal):
    def __init__(self, cmd: StrAttr):
        """Wrap a command for deferred resolution.

        Args:
            cmd: The command. A literal, a `Tpl` rendered against the task
                context, or a callable taking it.
        """
        self._cmd = cmd

    def to_str(self, ctx: AnyContext) -> str:
        """Resolve the command against `ctx`."""
        return get_str_attr(ctx, self._cmd, "")


SingleCmdVal = AnyCmdVal | str | Callable[[AnyContext], str]
CmdVal = SingleCmdVal | list[SingleCmdVal]
