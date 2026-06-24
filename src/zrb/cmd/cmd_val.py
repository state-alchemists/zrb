from abc import ABC, abstractmethod
from collections.abc import Callable

from zrb.attr.type import StrAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_str_attr
from zrb.util.file import read_file


class AnyCmdVal(ABC):
    @abstractmethod
    def to_str(self, ctx: AnyContext) -> str:
        pass


class CmdPath(AnyCmdVal):
    def __init__(self, path: StrAttr, auto_render: bool = True):
        self._path = path
        self._auto_render = auto_render

    def to_str(self, ctx: AnyContext) -> str:
        file_path = get_str_attr(ctx, self._path, "", self._auto_render)
        return read_file(file_path)


class Cmd(AnyCmdVal):
    def __init__(self, cmd: StrAttr, auto_render: bool = True):
        self._cmd = cmd
        self._auto_render = auto_render

    def to_str(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._cmd, "", self._auto_render)


SingleCmdVal = AnyCmdVal | fstring | Callable[[AnyContext], str]
CmdVal = SingleCmdVal | list[SingleCmdVal]
