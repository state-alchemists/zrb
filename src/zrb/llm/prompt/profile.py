"""Model-adaptive prompt profiles.

A *profile* is a **preset**: a named binding of three axes — which sections
compose, how they are phrased, and which tools register (ADR-0075).
``LLM_PROFILE`` selects one:

- ``full`` — the whole rulebook and the whole tool surface, on the base prompts.
- ``lean`` — for small models (~5-14B): every section and every tool, on a
  lighter rulebook (``workflow.lean.md``) plus worked demonstrations
  (``examples.lean.md``).
- ``minimal`` — for very small models (~3B): a short section list
  (:data:`MINIMAL_SECTIONS`), a one-page rulebook (``workflow.minimal.md``) and
  a short tool surface (:data:`MINIMAL_TOOLS`).
- ``auto`` (default) — resolved from the model id (see
  :data:`DEFAULT_MODEL_PROFILES`), falling back to ``full``.

The three names sit on one axis — how much the model is asked to hold at once —
and order themselves: ``full`` > ``lean`` > ``minimal``. That is deliberate.
``terse``/``mini``/``micro`` mixed a prose register with two size words, named
the *largest* preset "terse", and collided with the vendor tier labels that
:data:`DEFAULT_MODEL_PROFILES` matches on.

A preset reaches the prompt through one file-naming convention and no other: a
section named ``foo`` resolves ``foo.{profile}.md`` and falls back to ``foo.md``
(``prompt.get_prompt``). So a preset only ships files for the sections whose
text actually changes, and there is exactly one place to look for them.

**On choosing a profile automatically.** A *family* name (``deepseek``, ``qwen``,
``llama``, …) says nothing about capability — those families span tiny instruct
models through frontier models — so zrb never infers strength from one. What it
does read is a **declared size token**: ``-7b`` is not a guess about the model,
it is the vendor stating the parameter count, and the same goes for the size
*tiers* vendors label explicitly (``mini``, ``nano``, ``haiku``, …). Those are
matched by :data:`DEFAULT_MODEL_PROFILES` so the small models that most need a
lighter rulebook actually receive one by default.

Override either way with one line:
``register_model_profile("my-model", "full")``, or set ``ZRB_LLM_PROFILE``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# The base ``*.md`` files are the unvaried phrasing, so ``full`` needs no variant
# files — every section resolves straight to the base.
FULL_PROFILE = "full"
LEAN_PROFILE = "lean"
MINIMAL_PROFILE = "minimal"


#: Built-in model-id patterns, consulted only after user declarations.
#:
#: Every entry keys off something the id *states* rather than something it hints
#: at: an explicit parameter count, or a vendor's own small-tier label. Larger
#: declared sizes (``-32b``, ``-70b``, ``-405b``) are deliberately not matched.
#: See ADR-0047 (the variant rule) and ADR-0075 (presets and selection).
#:
#: The two size bands are asymmetric on purpose. ``lean`` keeps every capability
#: and only reshapes prose, so a false positive is cheap — which is why vendor
#: small-tier labels resolve there. ``minimal`` *removes* sections and tools, so
#: a false positive costs real capability. Only a stated parameter count of 4B
#: or less selects it: a vendor label is never enough, because ``nano``/``tiny``
#: sit on models (``gpt-5-nano``) far more capable than a 3B local one. Declare
#: a local model into ``minimal`` explicitly when you want it:
#: ``register_model_profile("my-local-model", "minimal")``.
DEFAULT_MODEL_PROFILES: tuple[tuple[str, str], ...] = (
    # A stated parameter count of 4B or less: "3b", "1.5B", "qwen2.5:3b".
    (r"(?<![0-9])[1-4]\s*b(?![a-z0-9])", MINIMAL_PROFILE),
    # A stated parameter count of 5B-14B: "7b", "8B", "gemma-2-9b".
    (r"(?<![0-9])(?:[5-9]|1[0-4])\s*b(?![a-z0-9])", LEAN_PROFILE),
    # Vendor small-tier labels. ``micro`` is here rather than on MINIMAL_PROFILE
    # for the same reason as ``nano``: it is a label, and a label never selects
    # the preset that subtracts.
    (r"(?<![a-z])(mini|micro|nano|tiny|small|lite)(?![a-z])", LEAN_PROFILE),
    (r"(?<![a-z])haiku(?![a-z])", LEAN_PROFILE),
    # `flash` is deliberately absent: it is a *latency* tier, not a size one, and
    # it spans weak to strong (``gemini-2.5-flash`` is capable). Opt a specific
    # one in with ``register_model_profile("deepseek-v4-flash", "lean")``.
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


#: ``minimal``'s tool surface. Closed under docstring cross-reference (ADR-0056),
#: which is what sets the size: the obvious six (``Shell``, ``Read``, ``Write``,
#: ``Edit``, ``Grep``, ``LS``) leave four dangling references. ``Shell`` and
#: ``Grep`` route callers to ``Glob``/``RM``/``MV`` for work they decline, and
#: ``Shell``'s ``background=True`` hands back a handle only ``MonitorProcess``
#: can poll — advertising the parameter without the tool is a trap, not a
#: saving. Closing the set costs ~500 tokens.
#: ``test_common_tools.py`` pins the closure rather than trusting this comment.
MINIMAL_TOOLS = frozenset(
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

#: ``minimal``'s section list. The two omissions are the point: ``examples``
#: because ``workflow.minimal.md`` carries its own demonstrations inline, and
#: ``project_context`` because its instruction is to ``Read`` project docs in
#: full, which alone can exceed a ~3B model's effective window. ``workflow``
#: stays in the list and resolves to ``workflow.minimal.md`` through the variant
#: axis — ``lean`` needs no list at all for the same reason.
MINIMAL_SECTIONS = ("persona", "workflow", "system_context")

#: Profile → preset. Burden falls monotonically with the capability each preset
#: targets — see ``RULE_SECTIONS_BY_PRESET`` in ``test_section_composition.py``,
#: which pins that ordering rather than trusting this comment.
#:
#: Registering a fourth is a dict assignment: ``PRESETS["nano"] = Preset(...)``.
#: ``valid_profiles()`` derives from these keys, so a new entry is immediately
#: accepted by ``ZRB_LLM_PROFILE`` and by ``register_model_profile``.
PRESETS: dict[str, Preset] = {
    FULL_PROFILE: Preset(),
    LEAN_PROFILE: Preset(variant=LEAN_PROFILE),
    MINIMAL_PROFILE: Preset(
        sections=MINIMAL_SECTIONS, variant=MINIMAL_PROFILE, tools=MINIMAL_TOOLS
    ),
}


def valid_profiles() -> tuple[str, ...]:
    """The profile names ``ZRB_LLM_PROFILE`` accepts, derived from :data:`PRESETS`.

    A function rather than a constant so a preset registered after import is
    accepted too — ``PRESETS`` is the single source of truth for the set.
    """
    return tuple(PRESETS)


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
        if profile not in valid_profiles():
            raise ValueError(
                f"Unknown profile {profile!r}. Valid: {list(valid_profiles())}"
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

    Any name in :func:`valid_profiles` selects that preset directly. ``auto``
    (the default) — or any unrecognized value — consults
    :data:`model_profile_registry` (user declarations, then
    :data:`DEFAULT_MODEL_PROFILES`), falling back to ``full`` when nothing
    matches.
    """
    value = (profile or "auto").strip().lower()
    if value in valid_profiles():
        return value
    return model_profile_registry.resolve(model) or FULL_PROFILE


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
