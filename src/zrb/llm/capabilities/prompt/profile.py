"""The small, explicit set of system-prompt profiles.

Profiles adjust the final ``profile`` section — ``profile.minimal.md``,
``profile.standard.md``, or ``profile.capable.md`` — and one tool:
``minimal`` registers no delegate (sub-agent) tools. They do not infer model
capability beyond the explicit ``auto`` mode, alter the core sections, or
otherwise change the tool surface.
"""

from __future__ import annotations

import re
from typing import Any

from zrb.config.config import CFG

MINIMAL_PROFILE = "minimal"
STANDARD_PROFILE = "standard"
CAPABLE_PROFILE = "capable"
DEFAULT_PROFILE = STANDARD_PROFILE

PROFILES = (MINIMAL_PROFILE, STANDARD_PROFILE, CAPABLE_PROFILE)

#: Declared parameter count (in billions) → profile, as ascending upper bounds.
#: A size above the last bound selects ``capable``; an id that declares no size
#: falls back to the default (``standard``).
SIZE_BANDS: tuple[tuple[float, str], ...] = (
    (4, MINIMAL_PROFILE),
    (14, STANDARD_PROFILE),
)

#: Vendor small-tier labels. Selects ``minimal`` only on a locally served model
#: (hosted ``gpt-5-nano`` is far more capable than a 3B local one), else ``standard``.
SMALL_TIER_LABELS: tuple[str, ...] = (
    "mini",
    "micro",
    "nano",
    "tiny",
    "small",
    "lite",
    "haiku",
)

#: Provider prefixes that mean "this model runs on the user's own machine".
LOCAL_PROVIDERS: tuple[str, ...] = ("ollama:", "lmstudio:", "llamacpp:", "localai:")
#: Ollama's hosted tier carries this suffix, which disqualifies it as local.
_HOSTED_TIER = ":cloud"

# Captured whole so `deepseek-r1:1.5b` reads as 1.5B, not its trailing `5b`.
_DECLARED_SIZE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", re.I)
_SMALL_TIER = re.compile(rf"(?<![a-z])({'|'.join(SMALL_TIER_LABELS)})(?![a-z])", re.I)


def builtin_profile(model_id: str) -> str | None:
    """Profile declared by *model_id* (size, then small-tier label), or ``None``."""
    size = _declared_size(model_id)
    if size is not None:
        return next(
            (profile for limit, profile in SIZE_BANDS if size <= limit),
            CAPABLE_PROFILE,
        )
    if not _SMALL_TIER.search(model_id):
        return None
    return MINIMAL_PROFILE if _is_local(model_id) else STANDARD_PROFILE


def _is_local(model_id: str) -> bool:
    """Whether *model_id* names a locally-served model rather than a hosted one."""
    lowered = model_id.lower()
    if _HOSTED_TIER in lowered:
        return False
    return any(lowered.startswith(prefix) for prefix in LOCAL_PROVIDERS)


def _declared_size(model_id: str) -> float | None:
    """Parameter count in billions stated by *model_id*, or ``None``."""
    match = _DECLARED_SIZE.search(model_id)
    return float(match.group(1)) if match else None


def resolve_profile(profile: str | None, model: Any | None = None) -> str:
    """Return a supported profile; ``auto`` consults :func:`builtin_profile`, else ``standard``."""
    value = (profile or DEFAULT_PROFILE).strip().lower()
    if value in PROFILES:
        return value
    if value == "auto":
        return builtin_profile(_model_id(model)) or DEFAULT_PROFILE
    return DEFAULT_PROFILE


def active_profile(model: Any | None = None) -> str:
    """Return the profile ``LLM_PROFILE`` selects for *model* (default ``CFG.LLM_MODEL``)."""
    if model is None:
        model = CFG.LLM_MODEL
    return resolve_profile(CFG.LLM_PROFILE, model)


def _model_id(model: Any | None) -> str:
    """Full model identifier exactly as configured, or ``""``."""
    if model is None:
        return ""
    if isinstance(model, str):
        return model.strip()
    name = getattr(model, "model_name", "")
    return name.strip() if isinstance(name, str) else ""
