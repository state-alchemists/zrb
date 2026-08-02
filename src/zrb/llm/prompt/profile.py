"""Model-adaptive prompt profiles.

A *profile* controls how each section is phrased and which optional sections are
composed, independent of *which* sections appear (that is
``LLM_INCLUDE_SECTIONS``). ``LLM_PROFILE`` selects one:

- ``terse`` — the concise, principle-led base prompts.
- ``mini`` — the profile for small models: the same rules plus worked
  demonstrations (``examples.mini.md``). Never extra rules (ADR-0091).
- ``auto`` (default) — ``mini`` when the model id declares a small size,
  ``terse`` otherwise (see :data:`DEFAULT_MODEL_PROFILES`, ADR-0093).

The base ``*.md`` files **are** the ``terse`` profile; other profiles are variant
overlays resolved with fallback (a missing variant transparently uses the base
file — see ``prompt.get_prompt``). This keeps shared rules in one place and forks
only the sections whose phrasing actually changes.

**On choosing a profile automatically.** A *family* name (``deepseek``, ``qwen``,
``llama``, …) says nothing about capability — those families span tiny instruct
models through frontier models — so zrb still never infers strength from one.
What it does read is a **declared size token**: ``-7b`` is not a guess about the
model, it is the vendor stating the parameter count, and the same goes for the
size *tiers* vendors label explicitly (``mini``, ``nano``, ``haiku``, ``flash``,
…). Those are matched by :data:`DEFAULT_MODEL_PROFILES` so the small models that
most need worked examples actually receive them by default.

The asymmetry makes the default safe: under ADR-0091 the ``mini`` profile
adds *demonstrations only* — never extra rules — so a false positive costs some
example tokens, while a false negative costs a weak model the one adaptation the
evidence supports. Override either way with one line:
``register_model_profile("my-model", "terse")``, or set ``ZRB_LLM_PROFILE``.
"""

from __future__ import annotations

import re
from typing import Any

# The base ``*.md`` files are written in the terse, principle-led register, so
# ``terse`` needs no variant files — it resolves straight to the base.
BASE_PROFILE = "terse"
MINI_PROFILE = "mini"
VALID_PROFILES = (BASE_PROFILE, MINI_PROFILE)


#: Built-in model-id patterns, consulted only after user declarations.
#:
#: Every entry keys off something the id *states* rather than something it hints
#: at: an explicit parameter count at or below ~14B, or a vendor's own
#: small-tier label. Larger declared sizes (``-32b``, ``-70b``, ``-405b``) are
#: deliberately not matched — the regex accepts 1–14 only. See ADR-0093.
DEFAULT_MODEL_PROFILES: tuple[tuple[str, str], ...] = (
    # A stated parameter count of 14B or less: "7b", "8B", "gemma-2-9b".
    (r"(?<![0-9])(?:[1-9]|1[0-4])\s*b(?![a-z0-9])", MINI_PROFILE),
    # Vendor small-tier labels.
    (r"(?<![a-z])(mini|nano|tiny|small|lite)(?![a-z])", MINI_PROFILE),
    (r"(?<![a-z])haiku(?![a-z])", MINI_PROFILE),
    # `flash` is deliberately absent: it is a *latency* tier, not a size one, and
    # it spans weak to strong (``gemini-2.5-flash`` is capable). Opt a specific
    # one in with ``register_model_profile("deepseek-v4-flash", "mini")``.
)


class ModelProfileRegistry:
    """Map of model-name patterns to prompt profiles, in two tiers.

    User declarations come first, most-recently-declared winning;
    :data:`DEFAULT_MODEL_PROFILES` is consulted only when none match, so a
    single ``register_model_profile`` call in ``zrb_init.py`` overrides a
    built-in either way. Consulted only by the ``auto`` profile. Mirrors
    ``model_capabilities`` (``capabilities.py``).
    """

    def __init__(self, defaults: tuple[tuple[str, str], ...] | None = None) -> None:
        self._overrides: list[tuple[str, str]] = []
        self._defaults = DEFAULT_MODEL_PROFILES if defaults is None else defaults

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
        """Return the profile for *model*, or ``None`` if nothing matches.

        User declarations are tried before the built-in defaults, so declaring a
        pattern always wins over a shipped one.
        """
        name = _model_id(model)
        if not name:
            return None
        for pattern, profile in (*self._overrides, *self._defaults):
            if re.search(pattern, name, re.IGNORECASE):
                return profile
        return None

    def clear(self) -> None:
        """Drop user declarations, keeping the built-in defaults. For tests.

        To exercise the no-mapping fallback, construct an isolated registry
        instead — ``ModelProfileRegistry(defaults=())`` — rather than stripping
        the singleton's defaults, which would leak into every later test.
        """
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

    ``terse``/``mini`` select that profile directly. ``auto`` (the default)
    — or any unrecognized value — consults :data:`model_profile_registry` (user
    declarations, then :data:`DEFAULT_MODEL_PROFILES`), falling back to the
    ``terse`` base when nothing matches.
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
