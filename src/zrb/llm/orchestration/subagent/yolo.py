"""Build a live YOLO-mode inheritance checker for sub-agents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from zrb.config.config import CFG
from zrb.llm.capabilities.permission import ALLOW, ASK, DENY


def make_yolo_inheritance_checker() -> Callable[..., bool]:  # noqa: C901 -- factory
    """Return a callable that reports the current effective YOLO mode.

    mccabe sums the nested closure into this function's score while radon scores
    each function separately (near-trivial on its own), so the factory carries
    `# noqa: C901` rather than the ratchet being raised for it.
    """
    # lazy: tests patch `zrb.llm.contracts.shared.agent_state.get_current_*` and
    # rely on the patch taking effect inside the closure. Hoisting would
    # bind these names at module-load and bypass the mocks.
    # lazy: tests patch zrb.llm.capabilities.permission.get_effective_policy; hoisting
    # would bind the name at this module's load time and bypass the mock.
    from zrb.llm.capabilities.permission import get_effective_policy
    from zrb.llm.contracts.shared.agent_state import get_current_ui, get_current_yolo
    from zrb.llm.engine.agent.run.hard_asks import (
        get_llm_tool_name,
        is_hard_ask_call,
    )
    from zrb.llm.engine.agent.run.tool_capabilities import get_tool_capability

    def check_yolo_inheritance(tool_def: Any = None, args: dict | None = None) -> bool:
        # Approval precedence (matches chat/task.py check_yolo):
        #   hard ask:    never auto-approved, whatever any level below says
        #   perm_policy: allow→auto-approve, deny→auto-approve (gate blocks),
        #                ask→defer to tool-policy / yolo cascade
        #   tool_policy: handled in _resolve_approval
        #   yolo:        handled in _resolve_approval
        if is_hard_ask_call(get_llm_tool_name(tool_def), args):
            # Leaving the sandbox and writing the MCP config are a human's
            # decision (ADR-0065, ADR-0146) — above the policy, not only above
            # yolo: an `allow` that covered one would be the same hole one level up.
            return False
        policy = get_effective_policy()
        if policy is not None:
            tool_name = (
                getattr(tool_def, "name", str(tool_def)) if tool_def is not None else ""
            )
            # By name, the same map the cascade reads: a capability tag lives on
            # the registered callable, and a `tool_def` here may not be it.
            result = policy.decide(
                tool_name, get_tool_capability(tool_name), args or {}
            )
            if result is not None:
                if result == ALLOW:
                    return True
                if result == DENY:
                    return True  # auto-approved (gate blocks at execution)
                if result == ASK:
                    return False  # explicit policy ASK is a 'hard ask'
            # fallback to YOLO only if policy has no matching rule
        yolo_val = get_current_yolo()
        if isinstance(yolo_val, bool):
            if yolo_val:
                return True
        elif isinstance(yolo_val, frozenset):
            # Selective YOLO is definitive: only the named tools bypass
            # approval. Return membership directly instead of falling through
            # to the UI's `yolo` (a non-empty frozenset is truthy and would
            # otherwise auto-approve tools the selection never listed). This
            # mirrors chat/task.py check_yolo, which has no UI fallback.
            if tool_def is None:
                return False
            tool_name = getattr(tool_def, "name", str(tool_def))
            return tool_name in yolo_val
        try:
            ui = get_current_ui()
            if ui is not None:
                return bool(ui.tools.yolo)
        except Exception as e:
            CFG.LOGGER.debug(f"Could not read UI yolo state: {e}")
        return False

    return check_yolo_inheritance
