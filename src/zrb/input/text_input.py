from .base_input import BaseInput
from collections.abc import Callable
from ..context.shared_context import SharedContext
from ..config import DEFAULT_EDITOR
import tempfile
import subprocess


class TextInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: str | Callable[[SharedContext], str] = "",
        auto_render: bool = True,
        allow_empty: bool = True,
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

    def _prompt_cli_str(self, shared_ctx: SharedContext) -> str:
        prompt_message = f"{self.comment_start}{super().prompt_message}{self.comment_end}\n"
        default_value = self._get_default_str(shared_ctx)
        with tempfile.NamedTemporaryFile(delete=False, suffix=self._extension) as temp_file:
            temp_file_name = temp_file.name
            temp_file.write(prompt_message.encode())
            # Pre-fill with default content
            if default_value:
                temp_file.write(default_value.encode())
            temp_file.flush()
        # Open the editor
        subprocess.call([self._editor, temp_file_name])
        # Read the edited content
        with open(temp_file_name, "r") as temp_file:
            edited_content = temp_file.read().strip()
            parts = edited_content.split(prompt_message)
            if len(parts) == 2 and parts[0].strip() == "":
                edited_content = parts[1]
        return edited_content.strip() if edited_content.strip() else default_value
