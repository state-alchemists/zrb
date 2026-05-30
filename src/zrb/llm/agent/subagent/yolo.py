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

    def check_yolo_inheritance(tool_def: Any = None) -> bool:
        yolo_val = get_current_yolo()
        if isinstance(yolo_val, bool):
            if yolo_val:
                return True
        elif isinstance(yolo_val, frozenset):
            if tool_def is not None:
                tool_name = getattr(tool_def, "name", str(tool_def))
                if tool_name in yolo_val:
                    return True
        try:
            ui = get_current_ui()
            if ui is not None and hasattr(ui, "yolo"):
                return bool(ui.yolo)
        except Exception:
            pass
        return False

    return check_yolo_inheritance
