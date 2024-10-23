from collections.abc import Callable
from ..session.context import Context


class CmdResult:
    def __init__(self, output: str, error: str):
        self.output = output
        self.error = error

    def __str__(self) -> str:
        return self.output


class CmdPath:
    def __init__(
        self, path: str, auto_render_content: bool = True, auto_render_path: bool = True
    ):
        self._path = path
        self._auto_render_content = auto_render_content
        self._auto_render_path = auto_render_path

    def read(self, context: Context) -> str:
        file_path = context.render(self._path) if self._auto_render_path else self._path
        with open(file_path) as file:
            content = file.read()
        return context.render(content) if self._auto_render_content else content


class Cmd:
    def __init__(self, cmd: str, auto_render: str):
        self._cmd = cmd
        self._auto_render = auto_render

    def render(self, context: Context) -> str:
        return context.render(self._cmd) if self._auto_render else self._cmd


SingleCmdVal = Cmd | CmdPath | str | Callable[[Context], str]
CmdVal = SingleCmdVal | list[SingleCmdVal]
