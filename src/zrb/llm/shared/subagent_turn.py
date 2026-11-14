"""One sub-agent turn, run one way.

A delegated sub-agent is asked to work from two places: the delegate tool starts
a turn, and a live session continues one after a human writes into it. Both are
the same call into the engine under the same grant, and they had drifted — a
different limiter, a different way of passing `yolo`, and a captured authority
that one of them honoured and the other never had. The drift cannot be kept in
step by hand, so the call exists once, here.

It sits at L0 because both sides need it and neither may import the other: the
delegate tool is a capability (L1) and the live session is orchestration (L3).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zrb.llm.shared.agent_runner import run_agent
from zrb.llm.shared.agent_state import (
    current_approval_channel,
    current_tool_confirmation,
)
from zrb.llm.shared.usage_log import COMPONENT_SUBAGENT, usage_component
from zrb.util.contextvar_scope import scoped

if TYPE_CHECKING:
    from zrb.llm.agent.run.authority_snapshot import AuthoritySnapshot
    from zrb.llm.agent.types import ModelMessage
    from zrb.llm.config.limiter import LLMLimiter
    from zrb.llm.ui.any_ui import AnyUI

# The five settings a captured delegation carries, and the argument each one
# becomes on `run_agent`.
_GRANT_FIELDS = (
    "permission_policy",
    "sandbox_policy",
    "hook_manager",
    "tool_confirmation",
    "approval_channel",
)


@dataclass(frozen=True)
class SubAgentTurn:
    """What one sub-agent turn needs, named once.

    ``authority`` is the grant a *delayed* turn resumes under — one that runs
    after the delegation's own scope has exited. A turn that starts inside its
    parent's run leaves it ``None`` and inherits whatever is ambient, which is
    the same grant, still bound.
    """

    agent: object
    message: str
    ui: "AnyUI"
    # The scope whose file reads this turn owns; a continuation reuses the
    # delegation's, so it remembers what earlier turns already read.
    run_scope: str
    limiter: "LLMLimiter"
    history: "list[ModelMessage]" = field(default_factory=list)
    authority: "AuthoritySnapshot | None" = None
    # Started where no parent run is bound, but still a sub-agent's turn.
    nested: bool = False
    # The per-call override a delegation tool may pass; `None` inherits.
    yolo: bool | None = None


async def run_subagent_turn(turn: SubAgentTurn) -> "tuple[object, list[object]]":
    """Run *turn* on the engine, tagged as the sub-agent's own work.

    The limiter is passed in rather than looked up here: both callers hand it
    the running one, and `zrb.llm.config` reads `zrb.llm.shared`, so reaching
    for it from this side would make the two units import each other.
    """
    authority = turn.authority
    with _bind_captured_approval(authority), usage_component(COMPONENT_SUBAGENT):
        return await run_agent(
            agent=turn.agent,
            message=turn.message,
            message_history=turn.history,
            limiter=turn.limiter,
            ui=turn.ui,
            run_scope=turn.run_scope,
            nested=turn.nested,
            yolo=_granted_yolo(turn),
            **_granted_settings(authority),
        )


def _granted_yolo(turn: SubAgentTurn) -> bool | None:
    """The yolo the turn runs under: its own override, else what was captured."""
    if turn.yolo is not None:
        return turn.yolo
    return None if turn.authority is None else turn.authority.yolo


def _granted_settings(authority: "AuthoritySnapshot | None") -> dict[str, object]:
    """The captured grant as `run_agent` arguments; all `None` inherits."""
    settings: dict[str, object] = {}
    for name in _GRANT_FIELDS:
        settings[name] = None if authority is None else getattr(authority, name)
    return settings


@contextmanager
def _bind_captured_approval(
    authority: "AuthoritySnapshot | None",
) -> Generator[None]:
    """Bind the captured approval handler and channel for one turn.

    Passing them is not enough: `run_agent` reads a `None` argument as
    "inherit the ambient value", so a delegation captured with no handler
    would otherwise pick up whatever is bound when the turn runs.
    """
    if authority is None:
        yield
        return
    with (
        scoped(current_tool_confirmation, authority.tool_confirmation),
        scoped(current_approval_channel, authority.approval_channel),
    ):
        yield
