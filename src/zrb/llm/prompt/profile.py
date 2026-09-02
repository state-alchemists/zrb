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

#: Vendor small-tier labels. A label alone is not enough to select ``minimal``:
#: ``nano``/``tiny``/``micro`` sit on models (``gpt-5-nano``) far more capable
#: than a 3B local one. A label on a locally served model (:data:`LOCAL_PROVIDERS`)
#: selects ``minimal``; any other label selects ``standard``.
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
#: The one piece of context that changes what a small-tier label claims.
LOCAL_PROVIDERS: tuple[str, ...] = ("ollama:", "lmstudio:", "llamacpp:", "localai:")
#: Ollama's hosted tier carries this suffix, which disqualifies it as local.
_HOSTED_TIER = ":cloud"

# A parameter count as vendors write it: delimited, optionally fractional, and
# closed by a `b`. The count is captured whole and compared numerically, so
# `deepseek-r1:1.5b` reads as 1.5B rather than as its trailing `5b`.
_DECLARED_SIZE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", re.I)
_SMALL_TIER = re.compile(rf"(?<![a-z])({'|'.join(SMALL_TIER_LABELS)})(?![a-z])", re.I)


def builtin_profile(model_id: str) -> str | None:
    """Profile declared by *model_id* itself, or ``None`` if it declares none.

    A stated parameter count is the vendor declaring the size; the first count
    in the id wins. With no count, a small-tier label reaches ``minimal`` only
    when the model is also locally served (:data:`LOCAL_PROVIDERS`), and
    ``standard`` otherwise.
    """
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
    """Return a supported profile, falling back to ``standard``.

    An explicit name selects that profile. ``auto`` (or any unrecognized value)
    consults :func:`builtin_profile` against *model*'s id, falling back to
    ``standard`` when the id declares nothing. The fallback keeps a stale
    environment value from breaking prompt construction while giving every
    ordinary installation one stable default.
    """
    value = (profile or DEFAULT_PROFILE).strip().lower()
    if value in PROFILES:
        return value
    if value == "auto":
        return builtin_profile(_model_id(model)) or DEFAULT_PROFILE
    return DEFAULT_PROFILE


def active_profile(model: Any | None = None) -> str:
    """Return the profile selected by ``LLM_PROFILE`` for *model*.

    *model* is the model id (``str``) or a model object; when omitted it falls
    back to ``CFG.LLM_MODEL``. The one call every consumer makes — the
    ``PromptManager`` for the profile section, and tool registration for the
    ``minimal`` delegate restriction — so the knob and the model are read in
    one place.
    """
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
