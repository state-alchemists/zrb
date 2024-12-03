import os
import subprocess
import tempfile
from collections.abc import Callable

from zrb.config import DEFAULT_EDITOR
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput


class TextInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: str | Callable[[AnySharedContext], str] = "",
        auto_render: bool = True,
        allow_empty: bool = False,
        editor: str = DEFAULT_EDITOR,
        extension: str = ".txt",
        comment_start: str | None = None,
        comment_end: str | None = None,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default_str=default_str,
            auto_render=auto_render,
            allow_empty=allow_empty,
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

    def to_html(self, ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self._get_default_str(ctx)
        return "\n".join(
            [
                f'<textarea name="{name}" placeholder="{description}">',
                default,
                "</textarea>",
            ]
        )

    def _prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        prompt_message = (
            f"{self.comment_start}{super().prompt_message}{self.comment_end}"
        )
        prompt_message_eol = f"{prompt_message}\n"
        default_value = self._get_default_str(shared_ctx)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=self._extension
        ) as temp_file:
            temp_file_name = temp_file.name
            temp_file.write(prompt_message_eol.encode())
            # Pre-fill with default content
            if default_value:
                temp_file.write(default_value.encode())
            temp_file.flush()
        # Open the editor
        subprocess.call([self._editor, temp_file_name])
        # Read the edited content
        with open(temp_file_name, "r") as temp_file:
            edited_content = temp_file.read()
            parts = [text.strip() for text in edited_content.split(prompt_message, 1)]
            edited_content = "\n".join(parts).lstrip()
        os.remove(temp_file_name)
        return edited_content
