"""How the UI a chat session runs on gets put together."""

from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.assembly import assemble_ui
from zrb.llm.ui.multi import MultiUI


def _ui() -> MagicMock:
    """A stand-in UI that is its own display, like every UI that owns its surface."""
    ui = MagicMock()
    ui.input = ui.tools = ui
    ui.display = ui
    return ui


@pytest.fixture
def terminal_backend(monkeypatch):
    """Stand in for the default UI, recording what it was built with."""
    built: list = []

    class _FakeUI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.tool_call_handler = MagicMock()
            built.append(self)

    monkeypatch.setattr("zrb.llm.ui.default.ui.UI", _FakeUI)
    monkeypatch.setattr("zrb.llm.ui.default.app.lexer.CLIStyleLexer", MagicMock)
    return built


@pytest.fixture
def wired_channels(monkeypatch):
    """Record the channel a `MultiUI` was wired to, without reading its state."""
    wired: list = []
    monkeypatch.setattr(
        MultiUI, "set_approval_channel", lambda self, channel: wired.append(channel)
    )
    return wired


def test_a_single_ui_runs_alone_when_the_default_is_excluded():
    ui = _ui()

    assembled = assemble_ui(
        uis=[ui],
        default_kwargs={},
        include_default_ui=False,
        approval_channels=[],
    )

    assert assembled is ui


def test_several_uis_are_combined_into_one_multi_ui(monkeypatch, wired_channels):
    first, second = _ui(), _ui()
    channel = MagicMock()
    monkeypatch.setattr(
        "zrb.llm.approval.resolve_approval_channel", lambda channels: channel
    )

    assembled = assemble_ui(
        uis=[first, second],
        default_kwargs={},
        include_default_ui=False,
        approval_channels=[channel],
    )

    assert isinstance(assembled, MultiUI)
    assert assembled.children == [first, second]
    assert wired_channels == [channel]


def test_no_channel_means_none_is_wired(monkeypatch, wired_channels):
    monkeypatch.setattr(
        "zrb.llm.approval.resolve_approval_channel", lambda channels: None
    )

    assemble_ui(
        uis=[_ui(), _ui()],
        default_kwargs={},
        include_default_ui=False,
        approval_channels=[],
    )

    assert wired_channels == []


def test_no_ui_is_the_default_terminal_ui(terminal_backend):
    """A session with no UI of its own still runs on one."""
    assembled = assemble_ui(
        uis=[],
        default_kwargs={"assistant_name": "Ada"},
        include_default_ui=False,
        approval_channels=[],
    )

    assert assembled is terminal_backend[0]
    assert assembled.kwargs["assistant_name"] == "Ada"
    assert "output_lexer" in assembled.kwargs


def test_the_default_ui_joins_the_callers_uis(terminal_backend, monkeypatch):
    caller_ui = _ui()
    handlers: list = []
    monkeypatch.setattr(
        MultiUI, "set_tool_call_handler", lambda self, handler: handlers.append(handler)
    )

    assembled = assemble_ui(
        uis=[caller_ui],
        default_kwargs={},
        include_default_ui=True,
        approval_channels=[],
    )

    default_ui = terminal_backend[0]
    assert isinstance(assembled, MultiUI)
    assert assembled.children == [default_ui, caller_ui]
    assert handlers == [default_ui.tool_call_handler]


def test_a_callers_own_ui_never_builds_the_terminal_backend(monkeypatch):
    def _refuse(**kwargs):
        raise AssertionError("the default UI was built for a session that has one")

    monkeypatch.setattr("zrb.llm.ui.default.ui.UI", _refuse)
    ui = _ui()

    assembled = assemble_ui(
        uis=[ui],
        default_kwargs={},
        include_default_ui=False,
        approval_channels=[],
    )

    assert assembled is ui
