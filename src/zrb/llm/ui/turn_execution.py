"""One chat turn, run the way every UI runs one.

`BaseUI` and `MultiUI` share no ancestor below `AnyUI`, so each wrote the turn
itself — and the two copies had already drifted. The composite cleared
`last_result_data` when a turn began and the base never did, so after a failed
turn `display.last_output` still answered with the turn before it. A sequence
copied into two files cannot be kept in step, so it is written once, here.

The hosts differ in no step, only in *where* the turn's state and output live:
which conversation, which model, which status line, which surface receives the
answer. Every one of those is already answered by an `AnyUI` role — the session
role carries the model, the open conversation, the flags and the status line;
the display role carries the answer and the repaint — and `MultiUI` answers each
of them across its children. So this module reaches a role, never a child.

This sits beside `turn_snapshot.py` and `turn_hooks.py`: the snapshot taken
before a turn, the hooks around it, and the turn itself, one file each.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Union, cast

from zrb.context.shared_context import SharedContext
from zrb.llm.permission.state import (
    AgentMode,
    get_current_agent_mode,
    set_current_agent_mode,
)
from zrb.llm.ui.turn_snapshot import take_pre_turn_snapshot
from zrb.llm.util.spoken import shown_text
from zrb.session.session import Session
from zrb.util.cli.style import stylize_muted
from zrb.util.exception import exception_summary

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.base.ui import BaseUI
    from zrb.llm.ui.multi.multi_ui import MultiUI
    from zrb.session.any_session import AnySession

    # The two UIs that run a turn, and nothing else: `AnyUI` does not promise
    # `last_result_data` or `confirm_tool_execution`, because a UI that never
    # runs a turn has no use for either.
    TurnHost = Union[BaseUI, MultiUI]


async def run_turn(
    ui: TurnHost,
    llm_task: LLMTask,
    user_message: str,
    attachments: "list[UserContent] | None" = None,
) -> None:
    """Run one turn on *ui* and settle its answer.

    A cancelled turn is announced and re-raised; a failed one is written down
    and absorbed, because the queue loop is the caller and it has to keep taking
    messages. Either way the UI leaves the turn with no answer carried over from
    the one before it, out of its thinking state, and with fresh system info.
    """
    attachments = list(attachments or [])
    # A fresh turn has no answer yet: a failure must not leave `last_output`
    # answering with the previous turn's reply.
    ui.last_result_data = None
    # Clear a stale running-tool timer left by a cancelled turn.
    ui.end_tool_call()
    ui.set_thinking(True)
    try:
        timestamp = datetime.now().strftime("%H:%M")
        await take_pre_turn_snapshot(
            ui.snapshot_manager,
            ui.history_manager,
            ui.conversation_session_name,
            user_message,
            timestamp,
        )
        ui.append_to_output(f"\n🤖 {timestamp} >>\n")
        session = build_turn_session(ui, user_message, attachments)
        ui.append_to_output(stylize_muted("\n  🔢 Streaming response..."))
        # The agent inherits the mode `/plan` left on the UI.
        set_current_agent_mode(
            AgentMode.PLAN if ui.plan_mode_active else AgentMode.BUILD
        )
        llm_task.set_ui(ui)
        llm_task.tool_confirmation = cast(Any, ui.confirm_tool_execution)
        result_data = await llm_task.async_run(session)
        # Tools like EnterPlanMode change the mode in-run; keep the badge in step.
        ui.plan_mode_active = get_current_agent_mode() == AgentMode.PLAN
        if isinstance(result_data, str):
            ui.last_result_data = result_data
            ui.append_to_output("\n")
            # The answer keeps its `<spoken>` markers for speech; the surface
            # shows the whole reply without them.
            ui.display.append_answer(shown_text(result_data))
        conversation = ui.conversation
        if conversation is not None:
            conversation.schedule_auto_name(user_message)
    except asyncio.CancelledError:
        ui.append_to_output("\n[Cancelled]\n")
        raise
    except Exception as e:
        ui.append_to_output(f"\n[Error: {exception_summary(e)}]\n")
    finally:
        # Flag, then system info, then repaint, so the status bar never paints
        # a stale value.
        ui.set_thinking(False, repaint=False)
        await ui.session.update_system_info()
        ui.display.invalidate_ui()


def build_turn_session(
    ui: TurnHost,
    user_message: str,
    attachments: "list[UserContent]",
) -> AnySession:
    """Build the session a turn runs in, named and modelled as *ui* is."""
    session_input = {
        "message": user_message,
        "session": ui.conversation_session_name or "default",
        "yolo": ui.yolo,
        "attachments": attachments,
        "model": ui.model,
    }
    shared_ctx = SharedContext(
        input=session_input,
        print_fn=ui.append_to_output,
        is_web_mode=True,
    )
    return Session(shared_ctx)
