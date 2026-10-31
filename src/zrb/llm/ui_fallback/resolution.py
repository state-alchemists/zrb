"""Normalizing a UI argument without loading the presentation layer.

`StdUI` is the fallback a run uses when it has no UI, so it lives in L0 beside
the functions that construct it. A list of two or more UIs becomes the
presentation layer's `MultiUI`, registered from `ui/multi_ui.py`: a list that
long can only exist if those UI classes were imported.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.llm.ui_fallback.std_ui import StdUI

if TYPE_CHECKING:
    from zrb.llm.any_ui import AnyUI

_UI_COMBINER: Callable[[list[AnyUI]], AnyUI] | None = None
_MAIN_UI_GETTER: Callable[[AnyUI], AnyUI] | None = None


def register_ui_combiner(combiner: Callable[[list[AnyUI]], AnyUI]) -> None:
    """Register the presentation layer's combiner for two or more UIs."""
    global _UI_COMBINER
    _UI_COMBINER = combiner


def register_ui_main_getter(getter: Callable[[AnyUI], AnyUI]) -> None:
    """Register the presentation layer's way to unwrap a combined UI."""
    global _MAIN_UI_GETTER
    _MAIN_UI_GETTER = getter


def create_combined_ui(uis: AnyUI | list[AnyUI], fallback: AnyUI) -> AnyUI:
    """One UI for *uis*: itself, its only member, the combined UI, or *fallback*
    when the list is empty."""
    if not isinstance(uis, list):
        return uis
    if not uis:
        return fallback
    if len(uis) == 1:
        return uis[0]
    if _UI_COMBINER is None:
        raise RuntimeError(
            "[SYSTEM SUGGESTION] A list of several UIs needs `zrb.llm.ui`, "
            "which registers the combiner; import the UI package or pass a "
            "single UI."
        )
    return _UI_COMBINER(uis)


def resolve_ui(uis: AnyUI | list[AnyUI] | None = None) -> AnyUI:
    """One UI for *uis* (see `create_combined_ui`); stdout's `StdUI` when there
    is none."""
    if uis is None:
        return StdUI()
    return create_combined_ui(uis, fallback=StdUI())


def get_main_ui(ui: AnyUI) -> AnyUI:
    """*ui*'s primary member when it is a combined UI, else *ui*."""
    if _MAIN_UI_GETTER is None:
        return ui
    return _MAIN_UI_GETTER(ui)
