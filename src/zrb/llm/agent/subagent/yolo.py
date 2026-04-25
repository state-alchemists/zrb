"""YOLO-mode inheritance checker used when creating sub-agents.

A sub-agent should honor a parent's YOLO toggle even if it changes mid-run,
so we return a callable that reads the live state on each invocation rather
than a captured boolean. Order: parent xcom → contextvar → False.
"""

from __future__ import annotations

from typing import Any, Callable


def make_yolo_inheritance_checker() -> Callable[..., bool]:
    """Return a callable that reports the current effective YOLO mode.

    Resolution order:
    1. Parent's `xcom["yolo"]` if reachable via the current UI's context
    2. The `current_yolo` ContextVar (set at delegation time)
    3. `False`
    """
    from zrb.llm.agent.run.runtime_state import get_current_ui, get_current_yolo

    def check_yolo_inheritance(ctx_or_none: Any = None, *args, **kwargs) -> bool:
        if get_current_yolo():
            return True
        try:
            ui = get_current_ui()
            if ui is not None and hasattr(ui, "_ctx"):
                parent_ctx = ui._ctx
                if parent_ctx is not None and hasattr(parent_ctx, "xcom"):
                    if "yolo" in parent_ctx.xcom:
                        return parent_ctx.xcom["yolo"].get(False)
        except Exception:
            pass
        return False

    return check_yolo_inheritance
