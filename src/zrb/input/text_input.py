import os
import subprocess
import tempfile
from collections.abc import Callable

from zrb.config.config import CFG
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput
from zrb.util.cli.text import edit_text
from zrb.util.file import read_file


class TextInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: str | Callable[[AnySharedContext], str] = "",
        auto_render: bool = True,
        allow_empty: bool = False,
        allow_positional_parsing: bool = True,
        always_prompt: bool = True,
        editor: str | None = None,
        extension: str = ".txt",
        comment_start: str | None = None,
        comment_end: str | None = None,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default=default,
            auto_render=auto_render,
            allow_empty=allow_empty,
            allow_positional_parsing=allow_positional_parsing,
            always_prompt=always_prompt,
        )
        self._editor = editor
        self._extension = extension
        self._comment_start = comment_start
        self._comment_end = comment_end

    @property
    def comment_start(self) -> str:
        if self._comment_start is not None:
            return self._comment_start
        if self._extension.lower() in [".py", ".rb", ".sh"]:
            return "# "
        if self._extension.lower() in [".md", ".html"]:
            return "<!-- "
        return "//"

    @property
    def comment_end(self) -> str:
        if self._comment_end is not None:
            return self._comment_end
        if self._extension.lower() in [".md", ".html"]:
            return " -->"
        return ""

    @property
    def editor_cmd(self) -> str | None:
        if self._editor is not None:
            return self._editor
        if CFG.DEFAULT_EDITOR != "":
            return CFG.DEFAULT_EDITOR
        return None

    def to_html(self, shared_ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self.get_default_str(shared_ctx)
        return "\n".join(
            [
                f'<textarea name="{name}" placeholder="{description}">',
                default,
                "</textarea>",
            ]
        )

    def _prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        if self.editor_cmd is None or self.editor_cmd.strip() == "":
            return super()._prompt_cli_str(shared_ctx)
        prompt_message = super().prompt_message
        comment_prompt_message = (
            f"{self.comment_start}{prompt_message}{self.comment_end}"
        )
        default_value = self.get_default_str(shared_ctx)
        return edit_text(
            prompt_message=comment_prompt_message,
            value=default_value,
            editor=self.editor_cmd,
            extension=self._extension,
        )
