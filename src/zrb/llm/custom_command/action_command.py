from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.util.cli.style import stylize_error, stylize_muted
from zrb.util.exception import exception_summary

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI

logger = logging.getLogger(__name__)

Action = Callable[[dict[str, str], "BaseUI | None"], str | None | Awaitable[str | None]]


class ActionCommand(AnyCustomCommand):
    """A slash command that runs *action* instead of prompting the LLM.

    *action* receives the parsed arguments and the chat UI (``None`` when
    there is none yet), and returns the text to show the user, or ``None`` to
    show nothing. An async *action* runs as a background task of the UI, which
    cancels it when the session ends; its return value is shown when it
    finishes.

    ``can_run_while_thinking=True`` lets the command run while the model is
    mid-response. *complete_arg* maps what the user has typed of the first
    argument to the values to offer. ``panel_title`` shows the reply in a panel
    instead of the transcript, under that title, where the UI has one — a table
    or a long report would otherwise scroll away with the next turn.
    """

    def __init__(
        self,
        command: str,
        action: Action,
        args: list[str] | None = None,
        description: str | None = None,
        can_run_while_thinking: bool = False,
        complete_arg: Callable[[str], Iterable[str]] | None = None,
        panel_title: str | None = None,
    ):
        self._command = command
        self._action = action
        self._args = args if args is not None else []
        self._description = description
        self._can_run_while_thinking = can_run_while_thinking
        self._complete_arg = complete_arg
        self._panel_title = panel_title

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

    @property
    def can_run_while_thinking(self) -> bool:
        return self._can_run_while_thinking

    def get_prompt(self, kwargs: dict[str, str]) -> str:
        return ""

    def get_arg_completions(self, arg_prefix: str) -> list[str]:
        if self._complete_arg is None:
            return []
        return list(self._complete_arg(arg_prefix))

    def handle(self, kwargs: dict[str, str], ui: "BaseUI | None") -> str | None:
        result = self._action(kwargs, ui)
        if not inspect.isawaitable(result):
            return self._deliver(result or "", ui)
        if ui is None:
            close = getattr(result, "close", None)
            if callable(close):
                close()
            return f"{self.command} needs an interactive chat session."
        task = asyncio.ensure_future(result)
        ui.background_tasks.add(task)
        task.add_done_callback(lambda done: _show_result(done, ui, self._panel_title))
        return ""

    def _deliver(self, reply: str, ui: "BaseUI | None") -> str:
        """Hand *reply* to the UI, or return it for the caller to print.

        A panel reply must not also be returned: the caller prints what comes
        back, so the same table would appear twice. With no UI there is no
        panel to fill, and the text comes back as any other reply.
        """
        if not reply or self._panel_title is None or ui is None:
            return reply
        ui.show_panel(self._panel_title, reply)
        return ""


def _show_result(
    task: "asyncio.Task[Any]", ui: "BaseUI", panel_title: str | None = None
) -> None:
    ui.background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.debug("Action command failed", exc_info=exc)
        ui.append_to_output(stylize_error(f"\n  ❌ {exception_summary(exc)}\n"))
        return
    reply = task.result()
    if not reply:
        return
    if panel_title is None:
        ui.append_to_output(stylize_muted(f"\n  {reply}\n"))
        return
    ui.show_panel(panel_title, reply)
