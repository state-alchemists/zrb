import os
import subprocess
import tempfile
from collections.abc import Callable

from zrb.config import DEFAULT_EDITOR
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput
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
        editor: str = DEFAULT_EDITOR,
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
        prompt_message = super().prompt_message
        comment_prompt_message = (
            f"{self.comment_start}{prompt_message}{self.comment_end}"
        )
        comment_prompt_message_eol = f"{comment_prompt_message}\n"
        default_value = self.get_default_str(shared_ctx)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=self._extension
        ) as temp_file:
            temp_file_name = temp_file.name
            temp_file.write(comment_prompt_message_eol.encode())
            # Pre-fill with default content
            if default_value:
                temp_file.write(default_value.encode())
            temp_file.flush()
        # Open the editor
        subprocess.call([self._editor, temp_file_name])
        # Read the edited content
        edited_content = read_file(temp_file_name)
        parts = [
            text.strip() for text in edited_content.split(comment_prompt_message, 1)
        ]
        edited_content = "\n".join(parts).lstrip()
        os.remove(temp_file_name)
        print(f"{prompt_message}: {edited_content}")
        return edited_content
