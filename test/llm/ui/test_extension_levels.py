"""Every documented custom-UI extension level, built the documented way.

`docs/llm/llm-custom-ui.md` promises three levels, each defined by the exact
set of methods a subclass has to write: `SimpleUI` (`print`, `get_input`),
`EventDrivenUI` (`print`, `start_event_loop`), and `BaseUI` (`append_to_output`,
`ask_user`, `run_interactive_command`, `run_async`). Prose cannot check itself,
and it drifted twice before this file existed — `BaseUI`'s own docstring
advertised a level whose method count was two short, and `create_ui_factory`
passed a `config=` keyword no `BaseUI` subclass accepted, so the documented
one-line registration raised `TypeError` for two of the three levels.

So the promise is written as code here: each class below implements *only* what
its level's docs say to implement, and is registered the documented one-line
way. A method that becomes required, or a constructor keyword that gets
renamed, fails here rather than in a user's `zrb_init.py`.
"""

from unittest.mock import MagicMock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.ui import BaseUI, EventDrivenUI, SimpleUI, UIConfig, create_ui_factory


class SimpleLevelUI(SimpleUI):
    """Level 1 — the docs promise `print` and `get_input`, nothing else."""

    async def print(self, text: str, kind: str = "text") -> None: ...

    async def get_input(self, prompt: str) -> str:
        return ""


class EventDrivenLevelUI(EventDrivenUI):
    """Level 2 — the docs promise `print` and `start_event_loop`."""

    async def print(self, text: str, kind: str = "text") -> None: ...

    async def start_event_loop(self) -> None: ...


class BaseLevelUI(BaseUI):
    """Level 3 — the docs promise these four, and full control of the rest."""

    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs): ...

    async def ask_user(self, prompt: str) -> str:
        return ""

    async def run_interactive_command(self, cmd, shell=False): ...

    async def run_async(self): ...


LEVELS = [SimpleLevelUI, EventDrivenLevelUI, BaseLevelUI]


def build(ui_class, **factory_kwargs):
    """Register `ui_class` exactly as the docs show, then run the factory."""
    factory = create_ui_factory(ui_class, **factory_kwargs)
    return factory(
        ctx=SharedContext(),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        ui_commands={},
        initial_message="",
        initial_conversation_name="a-session",
        initial_yolo=False,
        initial_attachments=[],
    )


@pytest.mark.parametrize("ui_class", LEVELS, ids=lambda c: c.__name__)
def test_documented_level_builds_through_create_ui_factory(ui_class):
    # Arrange / Act
    ui = build(ui_class)
    # Assert
    assert isinstance(ui, ui_class)
    assert ui.conversation_session_name == "a-session"


@pytest.mark.parametrize("ui_class", LEVELS, ids=lambda c: c.__name__)
def test_documented_level_needs_no_further_overrides(ui_class):
    """A level's documented method set is the *whole* requirement."""
    # Arrange / Act / Assert
    assert ui_class.__abstractmethods__ == frozenset()


@pytest.mark.parametrize("ui_class", LEVELS, ids=lambda c: c.__name__)
def test_ui_config_reaches_every_level(ui_class):
    """`ui_config` is the keyword every UI takes — the one that broke before."""
    # Arrange / Act
    ui = build(ui_class, ui_config=UIConfig(assistant_name="Ada"))
    # Assert
    assert ui.assistant_name == "Ada"


@pytest.mark.parametrize("ui_class", LEVELS, ids=lambda c: c.__name__)
def test_shared_ui_config_is_not_mutated_across_runs(ui_class):
    """One config object registered once, reused by every session it serves."""
    # Arrange
    shared = UIConfig(assistant_name="Ada")
    # Act
    build(ui_class, ui_config=shared)
    # Assert
    assert shared.conversation_session_name == ""
