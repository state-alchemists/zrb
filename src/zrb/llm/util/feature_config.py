"""Filling an optional feature's config from `CFG` when a session starts,
registering a feature on a task once, and handing a feature the UI serving
its session.

Each field of such a config dataclass mirrors one `CFG` knob by name — field
``device`` of the camera config is `CFG.LLM_CAMERA_DEVICE` — and ``None``
means "use the knob". Reading happens here, at session start, never at
import (R3), so `zrb_init.py` may change the knobs after importing zrb.
"""

from __future__ import annotations

import logging
import weakref
from collections.abc import Callable
from dataclasses import fields, replace
from functools import wraps
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from zrb.config.config import CFG
from zrb.config.env_field import warn_deprecated
from zrb.llm.ambient_state import get_session_ownership_key

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI

T = TypeVar("T")
logger = logging.getLogger(__name__)


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
    """The chat session a feature registration belongs to (the ambient chat
    session id; empty in the single-session CLI)."""
    return get_session_ownership_key()


#: ``(class name, old field name)`` pairs already warned about, so a plugin
#: building a config per session warns once rather than every time.
_renamed_field_warnings: "set[tuple[str, str]]" = set()


def _warn_renamed_field(owner: str, old: str, new: str) -> None:
    """Say once that ``<owner>(<old>=...)`` belongs to *new* now."""
    if (owner, old) in _renamed_field_warnings:
        return
    _renamed_field_warnings.add((owner, old))
    warn_deprecated(f"{owner}({old}=...)", new)


def _renamed_field_property(owner: str, old: str, new: str) -> property:
    """A property that reads and writes *new* under the name *old*."""

    def read(config: object) -> object:
        _warn_renamed_field(owner, old, new)
        return getattr(config, new)

    def write(config: object, value: object) -> None:
        _warn_renamed_field(owner, old, new)
        setattr(config, new, value)

    return property(read, write)


def accepts_renamed_fields(**renamed: str) -> Callable[[type[T]], type[T]]:
    """Let a config dataclass answer to the field names it used to have.

    Written under ``@dataclass``, one keyword per old name::

        @accepts_renamed_fields(enable_tool="tool_enabled")
        @dataclass
        class CameraConfig: ...

    An old name stays a working constructor argument — mapped onto the field
    that replaced it — and reads or writes that field as an attribute, so an
    extension built against the previous name keeps configuring the feature and
    learns the new name from one warning, instead of failing with a
    ``TypeError`` the moment it is imported. A rename in a public constructor is
    still a rename: the warning is the migration notice a knob's deprecation
    line is for an environment file.
    """

    def decorate(cls: type[T]) -> type[T]:
        build = cls.__init__

        @wraps(build)
        def __init__(self: T, *args: object, **kwargs: object) -> None:
            for old, new in renamed.items():
                if old in kwargs:
                    _warn_renamed_field(cls.__name__, old, new)
                    kwargs.setdefault(new, kwargs.pop(old))
            build(self, *args, **kwargs)

        # `wraps` leaves `__wrapped__` behind, so `inspect.signature` still
        # reports the dataclass's real parameters rather than `*args, **kwargs`.
        setattr(cls, "__init__", __init__)
        for old, new in renamed.items():
            setattr(cls, old, _renamed_field_property(cls.__name__, old, new))
        return cls

    return decorate


class FeatureSessions(Generic[T]):
    """One value per chat session, created on first use and closed with the
    session.

    Keyed by session because one `LLMChatTask` serves every web connection.
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

        Running sessions are closed with their original *close* first, since
        the new one may not fit them.
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
    try:
        for sessions in list(_every_feature_sessions):
            try:
                sessions.close_session(session_key)
            except Exception as exc:
                # One feature failing to close must not keep the others (or
                # the session's UI) alive.
                logger.warning(f"Closing a feature session failed: {exc}")
    finally:
        _session_uis.pop(session_key, None)


# The UI serving each chat session. Hooks run on a pool thread with the
# ambient UI cleared, and triggers are called with no arguments, so this is
# how a feature reaches its session's UI.
_session_uis: "dict[str, AnyUI]" = {}


def set_session_ui(ui: "AnyUI") -> None:
    """Make *ui* the one serving the session asking now."""
    _session_uis[current_session_key()] = ui


def get_session_ui() -> "AnyUI | None":
    """The UI serving the session asking now, if one is running."""
    return _session_uis.get(current_session_key())


def reset_session_ui() -> None:
    """Forget the session's UI, once it stops running."""
    _session_uis.pop(current_session_key(), None)


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

    A second `enable_*` call reuses the registry, closing what the first left
    running.
    """
    per_task = _session_values.setdefault(task, {})
    sessions = per_task.get(feature)
    if not isinstance(sessions, FeatureSessions):
        sessions = FeatureSessions(create, close)
        per_task[feature] = sessions
        return sessions
    sessions.replace(create, close)
    return sessions
