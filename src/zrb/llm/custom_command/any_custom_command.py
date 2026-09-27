from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


class AnyCustomCommand(ABC):

    @property
    @abstractmethod
    def command(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def args(self) -> list[str]: ...

    @abstractmethod
    def get_prompt(self, kwargs: dict[str, str]) -> str: ...

    def handle(self, kwargs: dict[str, str], ui: "BaseUI | None") -> str | None:
        """Run the command in-process instead of prompting the LLM.

        Return ``None`` (the default) to send ``get_prompt(kwargs)`` to the
        LLM. Return a string to handle the command here: it is shown to the
        user (nothing is shown for ``""``) and no LLM turn starts.

        *ui* is the chat UI the command was typed into, or ``None`` when there
        is none yet (the initial ``--message`` of a session).
        """
        return None

    @property
    def can_run_while_thinking(self) -> bool:
        """Whether the command may run while the model is mid-response.

        ``False`` by default: most commands change session state and wait for
        the turn to finish.
        """
        return False

    def get_arg_completions(self, arg_prefix: str) -> list[str]:
        """Values to offer while the user types the first argument."""
        return []
