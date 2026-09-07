"""Slash-command handlers must be bound to the UI instance.

`BaseUI` publishes a `handle_<x>_command` method for every slash command and
is the documented extension point a user subclasses to customise one. That
override is only reached if `command_table()` binds the handler to the UI
instance.

Binding to the part that implements the command — for example
`self._conversation.handle_save_command` — resolves it off an object the
subclass is not in the lookup chain of. The override is skipped, with no
error and no output: the built-in runs instead.

Enforces ADR-0035's guarantee that an override of any owner method is honored
regardless of which part implements it.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui import SimpleUI, UIConfig


class _ProbeUI(SimpleUI):
    """Minimal concrete UI, plus an override of one command handler."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.overridden_with = []

    async def print(self, text: str, kind: str = "text") -> None: ...

    async def get_input(self, prompt: str) -> str:
        return ""

    def handle_save_command(self, text: str) -> bool:
        self.overridden_with.append(text)
        return True


@pytest.fixture
def ui():
    return _ProbeUI(
        ctx=Context(SharedContext(), "probe", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        config=UIConfig.default(),
    )


def test_every_command_handler_is_bound_to_the_ui_instance(ui):
    misbound = [
        f"{handler.__qualname__} is bound to "
        f"{type(getattr(handler, '__self__', None)).__name__}"
        for handler, *_ in ui.commands.command_table()
        if getattr(handler, "__self__", None) is not ui
    ]
    assert not misbound, (
        "Command handler(s) bound to something other than the UI instance. A "
        "subclass override of the same-named BaseUI method will be silently "
        "ignored. Bind to `base_ui.handle_x_command`, not "
        f"`self._part.handle_x_command`:\n  " + "\n  ".join(misbound)
    )


def test_a_subclass_override_actually_runs_when_the_command_is_typed(ui):
    """A subclass override of a command handler runs when the user types it."""
    ui.save_commands = ["/save"]
    asyncio.run(ui.dispatch_command("/save my-session"))
    assert ui.overridden_with == ["/save my-session"]
