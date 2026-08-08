"""Model-adaptive prompt profiles.

A *profile* is a **preset**: a named binding of three axes — which sections
compose, how they are phrased, and which tools register (ADR-0075).
``LLM_PROFILE`` selects one, and the names order themselves by how much the
model is asked to hold at once:

- ``full`` — every section, every tool, the base prompt files.
- ``lean`` — every section and tool on a lighter rulebook, for ~5-14B models.
- ``minimal`` — a short section list and a short tool surface, for ~4B and below.
- ``auto`` (default) — resolved from the model id by :func:`builtin_profile`.

A preset reaches the prompt through one file-naming convention and no other: a
section named ``foo`` resolves ``foo.{profile}.md`` and falls back to ``foo.md``
(``prompt.get_prompt``), so a preset ships files only for the sections whose
text actually changes.

Automatic selection reads what a model id *states*, never what it hints at. A
family name (``deepseek``, ``qwen``, ``llama``) spans tiny instruct models
through frontier ones, so it is ignored; a parameter count is the vendor
declaring the size, and so is a vendor's own small-tier label. Override either
way with ``register_model_profile("my-model", "full")`` or ``ZRB_LLM_PROFILE``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from zrb.config.config import CFG

# The base ``*.md`` files are the unvaried phrasing, so ``full`` needs no variant
# files — every section resolves straight to the base.
FULL_PROFILE = "full"
LEAN_PROFILE = "lean"
MINIMAL_PROFILE = "minimal"


#: Declared parameter count (in billions) → profile, as ascending upper bounds.
#: A size above the last bound selects nothing, so large models keep ``full``.
#:
#: The bands are asymmetric on purpose. ``lean`` keeps every capability and only
#: reshapes prose, so a false positive is cheap. ``minimal`` *removes* sections
#: and tools, so a false positive costs real capability — which is why only a
#: stated count reaches it, never a label (see :data:`SMALL_TIER_LABELS`).
SIZE_BANDS: tuple[tuple[float, str], ...] = (
    (4, MINIMAL_PROFILE),
    (14, LEAN_PROFILE),
)

#: Vendor small-tier labels, all resolving to ``lean``. A label is never enough
#: to select ``minimal``: ``nano``/``tiny``/``micro`` sit on models (``gpt-5-nano``)
#: far more capable than a 3B local one. Declare a local model into ``minimal``
#: explicitly instead: ``register_model_profile("my-local-model", "minimal")``.
#:
#: ``flash`` is deliberately absent — it is a *latency* tier that spans weak to
#: strong (``gemini-2.5-flash`` is capable). Opt one in with
#: ``register_model_profile("deepseek-v4-flash", "lean")``.
SMALL_TIER_LABELS: tuple[str, ...] = (
    "mini",
    "micro",
    "nano",
    "tiny",
    "small",
    "lite",
    "haiku",
)

# A parameter count as vendors write it: delimited, optionally fractional, and
# closed by a `b`. The decimal is the whole reason this is parsed rather than
# pattern-matched per band — `deepseek-r1:1.5b` reads as 1.5B, where a digit
# class matching `5b` read it as 5B and handed a 1.5B model the 5-14B preset.
_DECLARED_SIZE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", re.I)
_SMALL_TIER = re.compile(rf"(?<![a-z])({'|'.join(SMALL_TIER_LABELS)})(?![a-z])", re.I)


def builtin_profile(model_id: str) -> str | None:
    """Profile declared by *model_id* itself, or ``None`` if it declares none.

    A stated parameter count wins over a label: it is the more specific claim,
    and a model stating both (``qwen3-30b-a3b``) is stating that the larger
    number is what it is. The first count in the id is the one read.
    """
    size = _declared_size(model_id)
    if size is not None:
        return next((profile for limit, profile in SIZE_BANDS if size <= limit), None)
    return LEAN_PROFILE if _SMALL_TIER.search(model_id) else None


def _declared_size(model_id: str) -> float | None:
    """Parameter count in billions stated by *model_id*, or ``None``."""
    match = _DECLARED_SIZE.search(model_id)
    return float(match.group(1)) if match else None


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
#: saving. ``test_common_tools.py`` pins the closure rather than trusting this.
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
#: targets — ``test_section_composition.py`` pins that ordering rather than
#: trusting this comment.
#:
#: Registering a fourth is a dict assignment: ``PRESETS["nano"] = Preset(...)``.
#: :func:`valid_profiles` derives from these keys, so a new entry is immediately
#: accepted by ``ZRB_LLM_PROFILE`` and by :func:`register_model_profile`.
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
    """Model-id patterns declared by the user, tried before the built-ins.

    Most-recently-declared wins, and every declaration outranks
    :func:`builtin_profile`, so one ``register_model_profile`` call in
    ``zrb_init.py`` overrides a built-in in either direction. Consulted only by
    the ``auto`` profile. Mirrors ``model_capabilities`` (``capabilities.py``).
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
        if profile not in valid_profiles():
            raise ValueError(
                f"Unknown profile {profile!r}. Valid: {list(valid_profiles())}"
            )
        self._overrides.insert(0, (pattern, profile))

    def resolve(self, model: Any | None) -> str | None:
        """Return the profile for *model*, or ``None`` if nothing declares one."""
        name = _model_id(model)
        if not name:
            return None
        for pattern, profile in self._overrides:
            if re.search(pattern, name, re.IGNORECASE):
                return profile
        return builtin_profile(name)

    def clear(self) -> None:
        """Drop user declarations, keeping the built-ins. For tests."""
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
    :func:`builtin_profile`), falling back to ``full`` when nothing matches.
    """
    value = (profile or "auto").strip().lower()
    if value in valid_profiles():
        return value
    return model_profile_registry.resolve(model) or FULL_PROFILE


def active_preset(model: Any | None = None) -> Preset:
    """The preset in force for *model* under the configured ``LLM_PROFILE``.

    The one call every consumer of the three axes makes — ``PromptManager`` for
    sections and phrasing, ``apply_common_tools`` for the tool surface — so the
    knob and the model are read in one place rather than at each site.
    """
    return resolve_preset(resolve_profile(CFG.LLM_PROFILE, model))


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
