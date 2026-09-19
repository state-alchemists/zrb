"""Inert implementations of `AnyUI`'s state members and side-effect hooks.

`AnyUI` splits in two: six behavioral methods every UI performs, and
seventeen members describing what a *full* UI keeps — the model it talks to,
whether the assistant is mid-turn, which background tasks it owns, what the
primary child exposes to `MultiUI`. `BaseUI` implements all seventeen;
`StdUI`, `BufferedUI` and `MultiUI` track almost none of it, so they mix this
in instead of each writing seventeen stubs.

Bodies live here rather than on `AnyUI` because no `any_*.py` module in this
codebase carries an implementation — `.coveragerc` excludes those paths on
that basis, so a default written there would ship untested.

Per ADR-0035 this is a genuine `Mixin`, and keeps the suffix: every value it
reads is a `_uidefaults_`-prefixed attribute it declares and sets itself, it
defines no `__init__` a host must remember to call, and `background_tasks`
builds its own set on first access — so any class can mix it in. A host that
implements a member for real declares it and wins on MRO (`MultiUI` does this
for `is_thinking` and `tool_call_handler`).

`UIStateDefaults`, not `UIDefaults`: `UIConfig` lives in this same package and
holds the *user-facing* defaults — assistant name, greeting, slash-command
aliases. This class defaults the other thing entirely, `AnyUI`'s state half,
and the old name read like a second `UIConfig`.
"""

from __future__ import annotations

import asyncio
from typing import Any


class UIStateDefaultsMixin:
    """Default `AnyUI` state members for UIs that do not track them.

    Every default is the honest answer to "this UI has no such thing": `None`
    for the objects, `False` for the flags, a no-op for the side-effect hooks.
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
    _uidefaults_small_model: Any = None
    _uidefaults_multimodal_model: Any = None
    _uidefaults_conversation_session_name: str = ""
    _uidefaults_plan_mode_active: bool = False
    _uidefaults_last_output: str = ""

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
    def small_model(self) -> Any:
        return self._uidefaults_small_model

    @small_model.setter
    def small_model(self, value: Any) -> None:
        self._uidefaults_small_model = value

    @property
    def multimodal_model(self) -> Any:
        return self._uidefaults_multimodal_model

    @multimodal_model.setter
    def multimodal_model(self, value: Any) -> None:
        self._uidefaults_multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        return self._uidefaults_conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str) -> None:
        self._uidefaults_conversation_session_name = value

    @property
    def plan_mode_active(self) -> bool:
        return self._uidefaults_plan_mode_active

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool) -> None:
        self._uidefaults_plan_mode_active = value

    @property
    def last_output(self) -> str:
        """Nothing rendered, so nothing to report. Read-only, matching the
        `AnyUI` contract; a UI that tracks it declares its own setter."""
        return self._uidefaults_last_output

    @property
    def snapshot_manager(self) -> Any:
        """No snapshots of its own, so nothing to rewind to."""
        return None

    @property
    def history_manager(self) -> Any:
        """No history of its own; the session's manager lives on the primary."""
        return None

    @property
    def background_tasks(self) -> "set[asyncio.Task]":
        """One mutable set per instance, created on first access.

        Callers mutate the returned set directly (`default/lifecycle.py`
        `.add()`s and `.discard()`s on it), so every call must hand back the
        same object rather than a fresh one.
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
