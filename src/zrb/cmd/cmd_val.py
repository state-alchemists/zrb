from abc import ABC, abstractmethod
from collections.abc import Callable

from zrb.attr.type import fstring
from zrb.context.context import Context


class AnyCmdVal(ABC):
    @abstractmethod
    def to_str(self, ctx: Context) -> str:
        pass


class CmdPath(AnyCmdVal):
    def __init__(self, path: str, auto_render: bool = True):
        self._path = path
        self._auto_render = auto_render

    def to_str(self, ctx: Context) -> str:
        file_path = ctx.render(self._path) if self._auto_render else self._path
        with open(file_path) as file:
            return file.read()


class Cmd(AnyCmdVal):
    def __init__(self, cmd: str, auto_render: str):
        self._cmd = cmd
        self._auto_render = auto_render

    def to_str(self, ctx: Context) -> str:
        return ctx.render(self._cmd) if self._auto_render else self._cmd


SingleCmdVal = AnyCmdVal | fstring | Callable[[Context], str]
CmdVal = SingleCmdVal | list[SingleCmdVal]
