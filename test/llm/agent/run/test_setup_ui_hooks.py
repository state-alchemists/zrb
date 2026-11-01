"""`setup_print_and_events` against a UI that never implemented an optional hook.

The stream handler used to be wired only to the hooks a UI had. They are
declared on `AnyUI` now, so every one is wired; for a UI that implemented none,
the transcript must be exactly what it was with no hook wired.
"""

import asyncio
import json

from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ToolCallPart,
    ToolReturnPart,
)

from zrb.llm.agent.run.setup import setup_print_and_events
from zrb.llm.any_ui import AnyUI
from zrb.llm.ui_fallback.state_defaults import UIStateDefaultsMixin
from zrb.llm.util.stream_response import create_event_handler


class _BareUI(UIStateDefaultsMixin, AnyUI):
    """Implements the behavioral half only; mentions no optional hook."""

    def __init__(self):
        self.written: list[tuple[str, str]] = []

    async def ask_user(self, prompt, output_to_parent="", agent_id=None) -> str:
        return ""

    async def ask_user_choice(self, spec, agent_id=None) -> str:
        return ""

    def append_to_output(self, *values, **kwargs):
        text = "".join(str(v) for v in values) + kwargs.get("end", "\n")
        self.written.append((text, kwargs.get("kind", "text")))

    def stream_to_parent(self, *values, **kwargs):
        pass

    async def run_interactive_command(self, cmd, shell=False):
        return None

    async def run_async(self):
        return None


def _tool_events():
    call = FunctionToolCallEvent(
        part=ToolCallPart(
            tool_name="search_files",
            args=json.dumps({"query": "main.py"}),
            tool_call_id="call_1",
        )
    )
    result = FunctionToolResultEvent(
        part=ToolReturnPart(
            tool_name="search_files",
            content="Found: main.py, utils.py" * 20,
            tool_call_id="call_1",
        )
    )
    return [call, result]


def _transcript(handler, events):
    async def _drive():
        for event in events:
            await handler(event)

    asyncio.run(_drive())


def test_a_bare_ui_gets_the_transcript_it_got_with_no_hooks_wired():
    wired_ui = _BareUI()
    _print_fn, wired = setup_print_and_events(None, None, wired_ui)

    unwired_ui = _BareUI()
    unwired = create_event_handler(
        lambda text, kind: unwired_ui.append_to_output(text, end="", kind=kind),
        show_tool_call_detail=wired.show_tool_call_detail,
    )

    _transcript(wired, _tool_events())
    _transcript(unwired, _tool_events())

    assert wired_ui.written
    assert wired_ui.written == unwired_ui.written


def test_the_stream_column_reaches_a_bare_ui_as_a_no_op():
    ui = _BareUI()

    setup_print_and_events(None, None, ui)

    assert ui.written == []
