"""Model-adaptive prompt profiles.

A *profile* controls how each section is phrased and which optional sections are
composed, independent of *which* sections appear (that is
``LLM_INCLUDE_SECTIONS``). ``LLM_PROFILE`` selects one:

- ``terse`` — the concise, principle-led base prompts.
- ``explicit`` — a more directive register for weaker models: per-section
  phrasing variants where they exist (e.g. ``persona.explicit.md``) plus the
  ``examples`` section of worked few-shot blocks.
- ``auto`` (default) — resolves to ``terse`` unless a per-model profile has been
  declared (see :func:`register_model_profile`).

The base ``*.md`` files **are** the ``terse`` profile; other profiles are variant
overlays resolved with fallback (a missing variant transparently uses the base
file — see ``prompt.get_prompt``). This keeps shared rules in one place and forks
only the sections whose phrasing actually changes.

**On choosing a profile automatically.** There is no reliable way to measure a
model's capability from its identifier — family names (``deepseek``, ``qwen``,
``llama``, …) span tiny instruct models through frontier models, so a substring
match guesses, it does not detect. zrb therefore makes **no** strength inference
from the model id. ``auto`` resolves to the ``terse`` base unless a per-model
profile has been **declared** via :func:`register_model_profile` (mirroring the
curated, user-extensible ``model_capabilities`` registry). Set
``ZRB_LLM_PROFILE=explicit`` to force the directive profile for a weaker model,
or declare it once per pattern from ``zrb_init.py``.
"""

from __future__ import annotations

import re
from typing import Any

# The base ``*.md`` files are written in the terse, principle-led register, so
# ``terse`` needs no variant files — it resolves straight to the base.
BASE_PROFILE = "terse"
EXPLICIT_PROFILE = "explicit"
VALID_PROFILES = (BASE_PROFILE, EXPLICIT_PROFILE)


class ModelProfileRegistry:
    """User-extensible map of model-name patterns to prompt profiles.

    Empty by default — zrb ships no built-in model→profile guesses, because a
    model id does not reveal capability. Users declare their own mappings (e.g.
    for a known-small local model) from ``zrb_init.py``; most-recently declared
    wins. Consulted only by the ``auto`` profile. Mirrors ``model_capabilities``
    (``capabilities.py``).
    """

    def __init__(self) -> None:
        self._overrides: list[tuple[str, str]] = []

    def set(self, pattern: str, profile: str) -> None:
        """Declare the profile for models whose id matches *pattern*.

        *pattern* is a case-insensitive regex matched against the **full** model
        id exactly as configured — provider prefix and any tier suffix included
        (e.g. ``ollama:deepseek-v4-flash:cloud``). Nothing is stripped, so a
        substring like ``deepseek-v4-flash`` matches, and so does a
        provider-wide ``ollama:`` or a tier-wide ``:cloud``. *profile* must be a
        valid profile. Most recently declared patterns take priority.
        """
        if profile not in VALID_PROFILES:
            raise ValueError(
                f"Unknown profile {profile!r}. Valid: {list(VALID_PROFILES)}"
            )
        self._overrides.insert(0, (pattern, profile))

    def resolve(self, model: Any | None) -> str | None:
        """Return the declared profile for *model*, or ``None`` if none match."""
        name = _model_id(model)
        if not name:
            return None
        for pattern, profile in self._overrides:
            if re.search(pattern, name, re.IGNORECASE):
                return profile
        return None

    def clear(self) -> None:
        """Drop all declared mappings. Intended for tests."""
        self._overrides.clear()


#: Module-level singleton. Import this (or ``register_model_profile``) from user
#: code; construct the class only in isolated tests.
model_profile_registry = ModelProfileRegistry()


def register_model_profile(pattern: str, profile: str) -> None:
    """Declare the prompt profile for models matching *pattern* (see
    :meth:`ModelProfileRegistry.set`). Convenience wrapper over the singleton."""
    model_profile_registry.set(pattern, profile)


def resolve_profile(profile: str | None, model: Any | None) -> str:
    """Resolve the active profile from the ``LLM_PROFILE`` value and the model.

    ``terse``/``explicit`` select that profile directly. ``auto`` (the default)
    — or any unrecognized value — consults the user-declared
    :data:`model_profile_registry`, falling back to the ``terse`` base when no
    mapping matches. zrb makes no built-in capability guess from the model id.
    """
    value = (profile or "auto").strip().lower()
    if value in VALID_PROFILES:
        return value
    return model_profile_registry.resolve(model) or BASE_PROFILE


def _model_id(model: Any | None) -> str:
    """Full model identifier exactly as configured, or ``""``.

    Nothing is stripped — patterns match the id the user sees (e.g.
    ``ollama:deepseek-v4-flash:cloud``), so there is no surprise about which
    segment a regex applies to. ``cloud`` only matches if the pattern says so.
    """
    if model is None:
        return ""
    if isinstance(model, str):
        return model.strip()
    name = getattr(model, "model_name", "")
    return name.strip() if isinstance(name, str) else ""
