"""Model-adaptive prompt profiles.

A *profile* is a **preset**: a named binding of three axes — which sections
compose, how they are phrased, and which tools register (ADR-0075).
``LLM_PROFILE`` selects one:

- ``terse`` — the concise, principle-led base prompts, full tool surface.
- ``mini`` — for small models (~5-14B): the same sections and tools, plus
  worked demonstrations (``examples.mini.md``). Never extra rules (ADR-0047).
- ``micro`` — for very small models (~3B): a lean section list
  (:data:`MICRO_SECTIONS`) and a lean tool surface (:data:`MICRO_TOOLS`), on the
  base phrasing. The one preset that *subtracts*, which is why it does so by
  composition rather than by a variant overlay.
- ``auto`` (default) — resolved from the model id (see
  :data:`DEFAULT_MODEL_PROFILES`), falling back to ``terse``.

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

The asymmetry makes the default safe: under ADR-0047 the ``mini`` profile
adds *demonstrations only* — never extra rules — so a false positive costs some
example tokens, while a false negative costs a weak model the one adaptation the
evidence supports. Override either way with one line:
``register_model_profile("my-model", "terse")``, or set ``ZRB_LLM_PROFILE``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# The base ``*.md`` files are written in the terse, principle-led register, so
# ``terse`` needs no variant files — it resolves straight to the base.
BASE_PROFILE = "terse"
MINI_PROFILE = "mini"
MICRO_PROFILE = "micro"
VALID_PROFILES = (BASE_PROFILE, MINI_PROFILE, MICRO_PROFILE)


#: Built-in model-id patterns, consulted only after user declarations.
#:
#: Every entry keys off something the id *states* rather than something it hints
#: at: an explicit parameter count, or a vendor's own small-tier label. Larger
#: declared sizes (``-32b``, ``-70b``, ``-405b``) are deliberately not matched.
#: See ADR-0047 (the variant rule) and ADR-0075 (presets and selection).
#:
#: The two size bands are asymmetric on purpose. ``mini`` only *adds*
#: demonstrations, so a false positive costs example tokens — cheap, which is
#: why vendor small-tier labels resolve there. ``micro`` *removes* sections and
#: tools, so a false positive costs real capability. Only a stated parameter
#: count of 4B or less selects it: ``nano``/``tiny`` are vendor labels on models
#: (``gpt-5-nano``) far more capable than a 3B local one, so they stay on
#: ``mini``. Declare a local model into ``micro`` explicitly when you want it:
#: ``register_model_profile("my-local-model", "micro")``.
DEFAULT_MODEL_PROFILES: tuple[tuple[str, str], ...] = (
    # A stated parameter count of 4B or less: "3b", "1.5B", "qwen2.5:3b".
    (r"(?<![0-9])[1-4]\s*b(?![a-z0-9])", MICRO_PROFILE),
    # A stated parameter count of 5B-14B: "7b", "8B", "gemma-2-9b".
    (r"(?<![0-9])(?:[5-9]|1[0-4])\s*b(?![a-z0-9])", MINI_PROFILE),
    # Vendor small-tier labels.
    (r"(?<![a-z])(mini|nano|tiny|small|lite)(?![a-z])", MINI_PROFILE),
    (r"(?<![a-z])haiku(?![a-z])", MINI_PROFILE),
    # `flash` is deliberately absent: it is a *latency* tier, not a size one, and
    # it spans weak to strong (``gemini-2.5-flash`` is capable). Opt a specific
    # one in with ``register_model_profile("deepseek-v4-flash", "mini")``.
)


@dataclass(frozen=True)
class Preset:
    """What a profile binds: a section list, a phrasing variant, a tool surface.

    ``None`` on any field means "do not constrain this axis" — the configured
    ``LLM_INCLUDE_SECTIONS`` applies, the base prompt files apply, every
    registered tool applies. See ADR-0075.
    """

    sections: tuple[str, ...] | None = None
    variant: str | None = None
    tools: frozenset[str] | None = None


#: ``micro``'s tool surface. Closed under docstring cross-reference (ADR-0056),
#: which is what sets the size: the obvious six (``Shell``, ``Read``, ``Write``,
#: ``Edit``, ``Grep``, ``LS``) leave four dangling references. ``Shell`` and
#: ``Grep`` route callers to ``Glob``/``RM``/``MV`` for work they decline, and
#: ``Shell``'s ``background=True`` hands back a handle only ``MonitorProcess``
#: can poll — advertising the parameter without the tool is a trap, not a
#: saving. Closing the set costs ~500 tokens.
#: ``test_common_tools.py`` pins the closure rather than trusting this comment.
MICRO_TOOLS = frozenset(
    {
        "Shell",
        "Read",
        "Write",
        "Edit",
        "Grep",
        "LS",
        "Glob",
        "RM",
        "MV",
        "MonitorProcess",
    }
)

#: ``micro``'s section list. ``workflow_micro`` is a distinct *section*, not a
#: variant of ``workflow`` — subtracting via a variant is the move ADR-0047
#: rule 2 forbids, while dropping a section is already guarded and tested.
#: ``project_context`` is absent: its instruction is to ``Read`` project docs in
#: full, which alone can exceed a ~3B model's effective window.
MICRO_SECTIONS = ("persona", "workflow_micro", "system_context")

#: ``mini``'s section list: the full section set with a lighter rulebook.
#: ``mini`` keeps every capability (skills, todos, delegation, plan mode, the
#: full tool surface), so ``workflow_mini`` drops abstraction rather than
#: behaviour — the same rules with the precedence ladder flattened and the
#: decision ladders merged. Same reasoning as ``MICRO_SECTIONS`` for why this is
#: a section swap and not a ``workflow.mini.md`` variant.
MINI_SECTIONS = (
    "persona",
    "workflow_mini",
    "examples",
    "system_context",
    "project_context",
)

#: Profile → preset. Burden falls monotonically with the capability each preset
#: targets — see ``RULE_SECTIONS_BY_PRESET`` in ``test_section_composition.py``,
#: which pins that ordering rather than trusting this comment.
PRESETS: dict[str, Preset] = {
    BASE_PROFILE: Preset(),
    MINI_PROFILE: Preset(sections=MINI_SECTIONS, variant=MINI_PROFILE),
    MICRO_PROFILE: Preset(sections=MICRO_SECTIONS, tools=MICRO_TOOLS),
}


def resolve_preset(profile: str | None) -> Preset:
    """Return the :class:`Preset` bound to *profile*, or an unconstrained one.

    An unrecognized profile yields ``Preset()`` so a stale config degrades to
    the full surface rather than to a crippled one.
    """
    return PRESETS.get(profile or "", Preset())


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
