"""Filling an optional feature's config from `CFG` when a session starts, and
registering a feature on a task once.

Each field of such a config dataclass mirrors one `CFG` knob by name — field
``device`` of the camera config is `CFG.LLM_CAMERA_DEVICE` — and ``None``
means "use the knob". Reading happens here, at session start, never at
import (R3), so `zrb_init.py` may change the knobs after importing zrb.
"""

from __future__ import annotations

import weakref
from dataclasses import fields, replace
from typing import Any, TypeVar

from zrb.config.config import CFG

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


_registered: "weakref.WeakKeyDictionary[Any, dict[str, list[tuple[str, Any]]]]" = (
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
