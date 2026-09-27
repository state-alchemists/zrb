"""Filling an optional feature's config from `CFG` when a session starts, and
registering a feature on a task once.

Each field of such a config dataclass mirrors one `CFG` knob by name — field
``device`` of the camera config is `CFG.LLM_CAMERA_DEVICE` — and ``None``
means "use the knob". Reading happens here, at session start, never at
import (R3), so `zrb_init.py` may change the knobs after importing zrb.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any, Generic, TypeVar

from zrb.config.config import CFG
from zrb.llm.tool.ambient_state import get_session_ownership_key

T = TypeVar("T")


def resolve_from_cfg(config: T, prefix: str) -> T:
    """A copy of dataclass *config* with every ``None`` field read from
    `CFG.<prefix><FIELD_NAME>`."""
    values: dict[str, Any] = {}
    for field in fields(config):  # type: ignore[arg-type]
        value = getattr(config, field.name)
        if value is None:
            value = getattr(CFG, f"{prefix}{field.name.upper()}")
        # A copy, so a session editing a list never edits CFG's.
        values[field.name] = list(value) if isinstance(value, list) else value
    return replace(config, **values)  # type: ignore[type-var]


def current_session_key() -> str:
    """The chat session a feature registration belongs to.

    `get_session_ownership_key` is what the rest of the chat names a session's
    resources with. Called with no display name it reads the ambient chat
    session id, which the web runner scopes per connection and which the
    interactive CLI leaves empty because it serves one session per process.
    """
    return get_session_ownership_key()


class FeatureSessions(Generic[T]):
    """One value per chat session, created on first use and closed with the
    session.

    A task outlives the sessions it serves — one `LLMChatTask` answers every
    web chat connection — so state a feature carries between its own
    registrations is keyed by the session that owns it, not held in a closure
    over the task. Config is resolved per session for the same reason: a knob
    changed between two sessions has to reach the second one (ADR-0102).
    """

    def __init__(self, create: Callable[[], T], close: Callable[[T], None]) -> None:
        self._create = create
        self._close = close
        self._sessions: dict[str, T] = {}
        _every_feature_sessions.add(self)

    def get(self, session_key: str | None = None) -> T:
        """The value for *session_key*, or for the session asking now."""
        key = session_key or current_session_key()
        if key not in self._sessions:
            self._sessions[key] = self._create()
        return self._sessions[key]

    def replace(self, create: Callable[[], T], close: Callable[[T], None]) -> None:
        """Build every later session with *create*, closing the rest with
        *close*.

        A second `enable_*` call on the same task brings a new config, so the
        factory has to be the new one: keeping the old would leave the
        replacement half-done, with every session after this point built by the
        call being replaced.

        The sessions already running are closed with the callback that was
        installed for them, before the new one takes over — a `close` for the
        new config may not fit what is on its way out.
        """
        self.close_all()
        self._create = create
        self._close = close

    def close_session(self, session_key: str) -> None:
        """Close and forget one session's value, if it has one."""
        value = self._sessions.pop(session_key, None)
        if value is not None:
            self._close(value)

    def close_all(self) -> None:
        for session_key in list(self._sessions):
            self.close_session(session_key)


# Every registry, for `close_feature_sessions`.
_every_feature_sessions: "weakref.WeakSet[FeatureSessions[Any]]" = weakref.WeakSet()


def close_feature_sessions(session_key: str) -> None:
    """Close *session_key*'s value in every feature that holds one; called
    where a chat session ends — the interactive CLI's teardown and the web
    runner's session removal."""
    for sessions in list(_every_feature_sessions):
        sessions.close_session(session_key)


_registered: "weakref.WeakKeyDictionary[Any, dict[str, list[tuple[str, Any]]]]" = (
    weakref.WeakKeyDictionary()
)
_session_values: "weakref.WeakKeyDictionary[Any, dict[str, FeatureSessions[Any]]]" = (
    weakref.WeakKeyDictionary()
)


def replace_registration(
    task: Any, feature: str, registrations: "list[tuple[str, Any]]"
) -> None:
    """Register each ``(append_method, item)`` on *task*, first taking out what
    an earlier call for the same *feature* registered, so enabling a feature
    twice replaces it instead of running it twice. A task without the
    matching ``remove_`` method keeps the earlier item."""
    per_task = _registered.setdefault(task, {})
    for append_method, item in per_task.pop(feature, []):
        remove = getattr(task, append_method.replace("append_", "remove_", 1), None)
        if callable(remove):
            remove(item)
    for append_method, item in registrations:
        getattr(task, append_method)(item)
    per_task[feature] = registrations


def replace_feature_sessions(
    task: Any, feature: str, create: Callable[[], T], close: Callable[[T], None]
) -> "FeatureSessions[T]":
    """The one `FeatureSessions` *task* uses for *feature*, building every
    later session with *create*.

    Keyed by *feature*, the same key `replace_registration` uses, so a second
    `enable_*` call finds the registry its first call made, adopts the new
    config and closes what the earlier one left running rather than leaving a
    second speaker or microphone.
    """
    per_task = _session_values.setdefault(task, {})
    sessions = per_task.get(feature)
    if not isinstance(sessions, FeatureSessions):
        sessions = FeatureSessions(create, close)
        per_task[feature] = sessions
        return sessions
    sessions.replace(create, close)
    return sessions
