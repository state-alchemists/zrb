"""Inert implementations of `AnyUI`'s members, assembled one part per role.

For UIs that track none of that state (`StdUI`, `BufferedUI`, `MultiUI`), and the
fallback `BaseUI` inherits for any member it does not implement itself. Each
role's defaults live with the role they answer for (`fallback/defaults/`); this
module is the single mixin a host inherits, plus the one member that belongs to
the whole object rather than to a role.

Bodies live here, not on `AnyUI`, because `any_*.py` is excluded from coverage and
`AnyUI` stays a pure contract. A host that implements a member for real wins on
MRO.
"""

from __future__ import annotations

from typing import Any

from zrb.llm.ui.fallback.defaults import (
    UIDisplayDefaults,
    UIInputDefaults,
    UIPickerDefaults,
    UISessionDefaults,
    UIToolsDefaults,
)


class UIStateDefaultsMixin(
    UIDisplayDefaults,
    UIInputDefaults,
    UIPickerDefaults,
    UISessionDefaults,
    UIToolsDefaults,
):
    """Every inert default a UI that keeps no state needs, one part per role.

    The five accessors come from the parts, so a caller reaches a role on a bare
    UI and gets the object itself back. `multi_ui_parent` is the one member here
    that no role owns: it is the `MultiUI` link, which belongs to the whole.
    """

    _uidefaults_multi_ui_parent: Any = None

    @property
    def multi_ui_parent(self) -> Any:
        return self._uidefaults_multi_ui_parent

    @multi_ui_parent.setter
    def multi_ui_parent(self, parent: Any) -> None:
        self._uidefaults_multi_ui_parent = parent
