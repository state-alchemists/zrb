"""YOLO-mode inheritance checker used when creating sub-agents.

A sub-agent should honor a parent's YOLO toggle even if it changes mid-run,
so we return a callable that reads the live state on each invocation rather
than a captured boolean.  Resolution: current_yolo ContextVar → UI → False.

The ContextVar can hold ``bool`` (full on/off) or ``frozenset[str]``
(selective — only named tools bypass approval).  When it is a frozenset the
checker consults ``tool_def.name`` just like the parent's ``check_yolo``
closure in ``chat/task.py``.
"""

from __future__ import annotations

from typing import Any, Callable

from zrb.config.config import CFG


def make_yolo_inheritance_checker() -> Callable[..., bool]:
    """Return a callable that reports the current effective YOLO mode.

    Resolution order:
    1. ``current_yolo`` ContextVar (``bool | frozenset[str]``)
    2. ``get_current_ui().yolo`` (live xcom read, covers live toggles)
    3. ``False``
    """
    # lazy: tests patch `zrb.llm.agent.run.runtime_state.get_current_*` and
    # rely on the patch taking effect inside the closure. Hoisting would
    # bind these names at module-load and bypass the mocks.
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.agent.run.runtime_state import get_current_ui, get_current_yolo

    # lazy: permission is a leaf; kept local to mirror get_current_* deferral
    # and so tests patching either layer take effect inside the closure.
    from zrb.llm.permission import ALLOW, ASK, DENY, Capability, get_effective_policy

    def check_yolo_inheritance(tool_def: Any = None) -> bool:
        # Approval precedence (matches chat/task.py check_yolo):
        #   perm_policy: allow→auto-approve, deny→auto-approve (gate blocks),
        #                ask→defer to tool-policy / yolo cascade
        #   tool_policy: handled in _resolve_approval
        #   yolo:        handled in _resolve_approval
        policy = get_effective_policy()
        if policy is not None:
            tool_name = (
                getattr(tool_def, "name", str(tool_def)) if tool_def is not None else ""
            )
            result = policy.decide(tool_name, Capability.UNKNOWN, {})
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
            if ui is not None and hasattr(ui, "yolo"):
                return bool(getattr(ui, "yolo"))
        except Exception as e:
            CFG.LOGGER.debug(f"Could not read UI yolo state: {e}")
        return False

    return check_yolo_inheritance
