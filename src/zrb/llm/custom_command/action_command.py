from collections.abc import Callable

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand


class ActionCommand(AnyCustomCommand):
    """A slash command that runs *action* instead of prompting the LLM.

    *action* receives the parsed arguments and returns the text to show the
    user, or ``None`` to show nothing.
    """

    def __init__(
        self,
        command: str,
        action: Callable[[dict[str, str]], str | None],
        args: list[str] | None = None,
        description: str | None = None,
    ):
        self._command = command
        self._action = action
        self._args = args if args is not None else []
        self._description = description

    @property
    def command(self) -> str:
        return self._command

    @property
    def description(self) -> str:
        if self._description:
            return self._description
        return " ".join([self.command] + [f"<{a}>" for a in self.args])

    @property
    def args(self) -> list[str]:
        return self._args

    def get_prompt(self, kwargs: dict[str, str]) -> str:
        return ""

    def handle(self, kwargs: dict[str, str]) -> str | None:
        return self._action(kwargs) or ""
