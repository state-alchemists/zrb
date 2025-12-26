from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prompt_toolkit.completion import Completer


def get_tool_confirmation_completer(
    options: list[str], meta_dict: dict[str, str]
) -> "Completer":
    from prompt_toolkit.completion import Completer, Completion

    class ToolConfirmationCompleter(Completer):
        """Custom completer for tool confirmation that doesn't auto-complete partial words."""

        def __init__(self, options, meta_dict):
            self.options = options
            self.meta_dict = meta_dict

        def get_completions(self, document, complete_event):
            text = document.text.strip()
            # 1. Input is empty, OR
            # 2. Input exactly matches the beginning of an option
            if text == "":
                # Show all options when nothing is typed
                for option in self.options:
                    yield Completion(
                        option,
                        start_position=0,
                        display_meta=self.meta_dict.get(option, ""),
                    )
                return
            # Only complete if text exactly matches the beginning of an option
            for option in self.options:
                if option.startswith(text):
                    yield Completion(
                        option,
                        start_position=-len(text),
                        display_meta=self.meta_dict.get(option, ""),
                    )

    return ToolConfirmationCompleter(options, meta_dict)
