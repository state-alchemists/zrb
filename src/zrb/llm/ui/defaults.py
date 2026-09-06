"""Inert implementations of `AnyUI`'s optional half.

`AnyUI` declares sixteen members but only six of them are things every UI
genuinely does (asking, printing, running). The other ten describe state and side-effect hooks a
*full* UI keeps — the model it talks to, whether the assistant is mid-turn,
which background tasks it owns. `BaseUI` implements all seven for real; the
UIs that skip `BaseUI` and implement `AnyUI` directly (`StdUI`, `BufferedUI`,
`MultiUI`) have no use for most of them.

Before this existed, that gap was paid for at every call site: eleven
`hasattr(ui, ...)` probes across `multi_ui.py`, `default/lifecycle.py`,
`llm_task.py` and `agent/subagent/yolo.py`, each re-establishing at runtime a
contract the type system could not state. Mixing this in closes the gap so
callers can just call.

The bodies live here rather than on `AnyUI` because `any_*.py` files hold no
implementation anywhere in this codebase — `.coveragerc` excludes them on
exactly that basis, so a default written there would ship untested by
construction. Declaration in the interface, implementation here.

Per ADR-0035 this is a genuine `Mixin`: it reads no state it does not itself
set, so any class can mix it in, and a host that implements one of these for
real simply defines it and wins on MRO (`MultiUI` does this for `is_thinking`
and `tool_call_handler`).
"""

from __future__ import annotations

import asyncio
from typing import Any


class UIDefaultsMixin:
    """Default `AnyUI` state members for UIs that do not track them.

    Every default is the honest answer to "this UI has no such thing": `None`
    for the objects, `False` for the flags, a no-op for the repaint hook. That
    is the same answer the `hasattr` branches used to arrive at, minus the
    runtime probe.
    """

    # Class-level defaults. An instance assignment through the setters below
    # shadows them per instance, so these behave like ordinary attributes
    # without this mixin having to define an `__init__` its hosts would then
    # have to remember to call.
    #
    # `_uidefaults_`-prefixed because a host may keep its own field of the
    # obvious name for a member it implements for real — `BaseUI.__init__`
    # sets `_background_tasks` — and a bare name would collide with it.
    _uidefaults_is_thinking: bool = False
    _uidefaults_llm_task: Any = None
    _uidefaults_model: Any = None
    _uidefaults_multi_ui_parent: Any = None
    # Deliberately a `None` sentinel rather than `set()`: a mutable class
    # attribute is shared by every instance, so one UI's background tasks
    # would land in every other UI's set.
    _uidefaults_background_tasks: "set[asyncio.Task] | None" = None

    @property
    def is_thinking(self) -> bool:
        return self._uidefaults_is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._uidefaults_is_thinking = value

    @property
    def llm_task(self) -> Any:
        return self._uidefaults_llm_task

    @llm_task.setter
    def llm_task(self, value: Any) -> None:
        self._uidefaults_llm_task = value

    @property
    def model(self) -> Any:
        return self._uidefaults_model

    @model.setter
    def model(self, value: Any) -> None:
        self._uidefaults_model = value

    @property
    def yolo(self) -> bool | frozenset:
        """Never auto-approve. Read-only, matching the `AnyUI` contract."""
        return False

    @property
    def multi_ui_parent(self) -> Any:
        return self._uidefaults_multi_ui_parent

    @multi_ui_parent.setter
    def multi_ui_parent(self, parent: Any) -> None:
        self._uidefaults_multi_ui_parent = parent

    @property
    def tool_call_handler(self) -> Any:
        """No handler of its own; callers fall back to an approval channel."""
        return None

    @property
    def background_tasks(self) -> "set[asyncio.Task]":
        """A real per-instance set — callers `.add()` and `.discard()` on it.

        Handing back a fresh set each call would make `_track_background`
        silently drop every task it thinks it registered, so the set is
        created once on first access and kept.
        """
        if self._uidefaults_background_tasks is None:
            self._uidefaults_background_tasks = set()
        return self._uidefaults_background_tasks

    def invalidate_ui(self) -> None:
        """Repaint hook. A UI with no addressable surface has nothing to do."""

    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """No confirmations of its own to release."""

    def flush_to_parent(self) -> None:
        """Nothing buffered, so nothing to hand upward."""
