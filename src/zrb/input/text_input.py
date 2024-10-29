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
        extension: str = ".txt"
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

    def _prompt_cli_str(self, shared_ctx: SharedContext) -> str:
        default_value = self._get_default_str(shared_ctx)
        with tempfile.NamedTemporaryFile(delete=False, suffix=self._extension) as temp_file:
            temp_file_name = temp_file.name
            # Pre-fill with default content
            if default_value:
                temp_file.write(default_value.encode())
                temp_file.flush()
        # Open the editor
        subprocess.call([self._editor, temp_file_name])
        # Read the edited content
        with open(temp_file_name, "r") as temp_file:
            edited_content = temp_file.read().strip()
        return edited_content.strip() if edited_content.strip() else default_value
