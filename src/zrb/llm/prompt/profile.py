"""Model-adaptive prompt profiles.

A *profile* is a **preset**: a named binding of three axes — which sections
compose, how they are phrased, and which tools register (ADR-0049).
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
# closed by a `b`. The count is captured whole and compared numerically, so
# `deepseek-r1:1.5b` reads as 1.5B rather than as its trailing `5b`.
#: Provider prefixes that mean "this model runs on the user's own machine".
#:
#: The one piece of context that changes what a small-tier label claims. A vendor
#: shipping ``gpt-5-nano`` over an API is naming a tier in a lineup that starts
#: far above a 3B; someone running ``ollama:phi4-mini`` is running 3.8B of
#: weights on a laptop. Same label, two different assertions — which is why a
#: label alone still only reaches ``lean`` (see :data:`SMALL_TIER_LABELS`) and
#: only a label *plus* a local prefix reaches ``minimal``.
#:
#: Ollama's hosted tier is the exception inside the exception: ``ollama:`` there
#: prefixes frontier models, and those ids carry ``:cloud``, so it disqualifies.
LOCAL_PROVIDERS: tuple[str, ...] = ("ollama:", "lmstudio:", "llamacpp:", "localai:")
_HOSTED_TIER = ":cloud"

_DECLARED_SIZE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", re.I)
_SMALL_TIER = re.compile(rf"(?<![a-z])({'|'.join(SMALL_TIER_LABELS)})(?![a-z])", re.I)


def builtin_profile(model_id: str) -> str | None:
    """Profile declared by *model_id* itself, or ``None`` if it declares none.

    A stated parameter count wins over a label: it is the more specific claim,
    and a model stating both (``qwen3-30b-a3b``) is stating that the larger
    number is what it is. The first count in the id is the one read.

    With no count, a small-tier label reaches ``minimal`` only when the model is
    also locally served (:data:`LOCAL_PROVIDERS`), and ``lean`` otherwise.
    """
    size = _declared_size(model_id)
    if size is not None:
        return next((profile for limit, profile in SIZE_BANDS if size <= limit), None)
    if not _SMALL_TIER.search(model_id):
        return None
    return MINIMAL_PROFILE if _is_local(model_id) else LEAN_PROFILE


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


@dataclass(frozen=True)
class Preset:
    """What a profile binds: a section list, a phrasing variant, a tool surface.

    ``None`` on any field means "do not constrain this axis" — the configured
    ``LLM_INCLUDE_SECTIONS`` applies, the base prompt files apply, every
    registered tool applies. See ADR-0049.

    The tool axis has two forms because the two constrained presets want
    opposite things. ``tools`` is an allowlist: a closed, fixed surface, which
    is what ``minimal`` needs and what makes its closure checkable. ``drops`` is
    a denylist: everything registered *except* these, which is what ``lean``
    needs — it keeps the full surface and subtracts a few, so an allowlist would
    have to re-list every tool and would silently drop each new one from ``lean``
    until someone remembered to add it. Set at most one.
    """

    sections: tuple[str, ...] | None = None
    variant: str | None = None
    tools: frozenset[str] | None = None
    drops: frozenset[str] | None = None

    def __post_init__(self) -> None:
        # "Set at most one" was documented above and enforced nowhere, and
        # `admits` resolves the conflict by silently ignoring `drops` — so a
        # preset asking for "these ten tools, minus the journal" got the ten and
        # no warning. Rejected at construction rather than at registration,
        # because `PRESETS[name] = Preset(...)` bypasses `register_preset`.
        if self.tools is not None and self.drops is not None:
            raise ValueError(
                "Preset takes either tools (an allowlist) or drops (a denylist), "
                "not both. `tools` alone already excludes everything unlisted."
            )

    def admits(self, name: str) -> bool:
        """Whether a tool registered under *name* survives this preset."""
        if self.tools is not None:
            return name in self.tools
        return self.drops is None or name not in self.drops

    @property
    def constrains_tools(self) -> bool:
        """Whether this preset narrows the tool axis at all."""
        return self.tools is not None or self.drops is not None


#: ``minimal``'s tool surface. Closed under docstring cross-reference (ADR-0058),
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

#: What ``lean`` subtracts from the full surface: ~437 tokens of schema, ~18% of
#: the eager tool definitions a 5-14B model reads before it reads the request.
#: Regenerate with ``python llm-experiment/measure.py`` rather than editing by
#: hand — the earlier "~920 tokens" here and the "3,840 → 3,146" in ADR-0049
#: disagreed with each other because both were hand-derived once and never
#: recomputed.
#:
#: The journal trio goes because cross-session memory is the wrong thing to
#: spend a constrained model's tool budget on: it is not needed to finish the
#: turn, and ADR-0055 left no prompt prose to orphan. ``live_context`` stops
#: injecting the index to match (see ``render_journal_index``) — a preset that
#: drops the reader must not keep handing it something to read.
LEAN_DROPS = frozenset({"SearchJournal", "LogActivity", "WriteJournalNote"})

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
    LEAN_PROFILE: Preset(variant=LEAN_PROFILE, drops=LEAN_DROPS),
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


#: The rank-1 safety rules, as the alternative phrasings that count as carrying
#: each one. Concepts rather than sentences, so a custom rulebook may say it in
#: its own words. Deliberately a second copy of the table in
#: ``test_section_composition.py``: the test asserts the floor for the built-in
#: presets independently, and a shared table would let one wrong regex excuse
#: both.
_RANK_ONE_PATTERNS: dict[str, tuple[str, ...]] = {
    "secrets": (r"secret", r"credential", r"password", r"api key"),
    "tool output is not instructions": (
        r"data,?\s*not",
        r"ignore\s+\w+\s+instructions",
    ),
    "confirm destructive actions": (r"destructive", r"destroy", r"irreversible"),
}

#: Sections that carry rules, and so must still carry the safety floor. A preset
#: composing none of them is a preset with no rulebook, which
#: :func:`register_preset` reports separately.
_RULE_SECTIONS = ("persona", "workflow")


def register_preset(name: str, preset: Preset) -> None:
    """Register *preset* under *name*, making it a valid ``LLM_PROFILE`` value.

    ``PRESETS[name] = preset`` does the same thing and stays supported; this
    adds the checks that a bare assignment cannot make, because the three ways a
    custom preset goes wrong are all silent:

    1. **The prose falls back to ``full``.** A ``variant`` with no
       ``{section}.{variant}.md`` anywhere on the lookup path resolves to the
       base file, so a preset written for a 1B model quietly ships it the
       frontier rulebook. Warned per section, not raised: shipping a variant for
       only *some* sections is legitimate.
    2. **The safety floor goes missing.** Every built-in preset is pinned to
       Priority Order rank 1 by ``test_section_composition.py``; that test walks
       a hardcoded list of the three built-ins, so a custom preset inherits none
       of it. The same floor is checked here instead.
    3. **Both tool axes are set.** Rejected by :class:`Preset` itself.

    Overriding a built-in name is allowed — redefining ``lean`` for your own
    fleet is a legitimate use — and runs the same checks.

    Args:
        name: The ``ZRB_LLM_PROFILE`` value that selects this preset.
        preset: What the name binds.

    Raises:
        ValueError: *name* is empty or not a string, *preset* is not a
            :class:`Preset`, or *name* is ``auto`` (reserved for model-based
            resolution, so a preset under that name could never be selected).
    """
    # Typed as object so the runtime guard is not read as dead code: this is a
    # public entry point, and the value it protects lands in a module-level dict
    # that every later lookup trusts.
    candidate: object = preset
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Preset name must be a non-empty string, got {name!r}.")
    if not isinstance(candidate, Preset):
        raise ValueError(
            f"Expected a Preset for {name!r}, got {type(candidate).__name__}."
        )
    key = name.strip().lower()
    if key == "auto":
        raise ValueError(
            "'auto' is reserved: it means 'resolve from the model id', so a "
            "preset registered under it could never be selected. Register it "
            "under its own name and point models at it with "
            "register_model_profile()."
        )
    PRESETS[key] = preset
    for warning in _preset_warnings(preset):
        CFG.LOGGER.warning(f"register_preset({key!r}): {warning}")


def _preset_warnings(preset: Preset) -> list[str]:
    """What is off about *preset* but not fatal. Empty when it is sound."""
    # lazy: circular — prompt imports profile for FULL_PROFILE
    from zrb.llm.prompt.prompt import get_default_prompt, get_prompt

    # ``LLM_INCLUDE_SECTIONS`` is the parsed list; the ``DEFAULT_`` twin beside
    # it is the raw comma-separated string, and iterating that yields
    # characters, not section names.
    sections = preset.sections or tuple(CFG.LLM_INCLUDE_SECTIONS)
    warnings = []
    if preset.variant:
        missing = [
            section
            for section in sections
            if section in _RULE_SECTIONS
            and not get_default_prompt(f"{section}.{preset.variant}")
        ]
        if missing:
            warnings.append(
                f"variant {preset.variant!r} has no file for {missing}, so those "
                f"sections fall back to the base (`full`) text. Add "
                f"{missing[0]}.{preset.variant}.md under LLM_PROMPT_DIR."
            )
    composed = "\n".join(
        get_prompt(section, profile=preset.variant)
        for section in sections
        if section in _RULE_SECTIONS
    ).lower()
    if not composed.strip():
        warnings.append(
            f"composes no rule-carrying section ({' or '.join(_RULE_SECTIONS)}), "
            "so the model gets tools and context but no operating rules."
        )
        return warnings
    absent = [
        concept
        for concept, patterns in _RANK_ONE_PATTERNS.items()
        if not any(re.search(pattern, composed) for pattern in patterns)
    ]
    if absent:
        warnings.append(
            f"composed rulebook states no {absent}. Composition may drop method; "
            "it may never drop Priority Order rank 1 (ADR-0049)."
        )
    return warnings


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
    the ``auto`` profile.

    **Not a duplicate of ``model_capabilities`` (``llm/util/capabilities.py``),
    and not mergeable with it.** The two have the same shape and different
    keys, because they answer different questions:

    * A capability is a property of the *weights*. ``gpt-4o`` accepts images
      whether ``openai:`` or ``azure:`` serves it, so that registry strips the
      prefix and matches the bare name — which is what lets its built-in deny
      patterns be ``^``-anchored.
    * A profile is a property of the *deployment*. ``ollama:phi4-mini`` is 3.8B
      on a laptop; ``openai:gpt-5-nano`` is the entry tier of a hosted family.
      Same small-tier label, opposite conclusions, and only the prefix and the
      ``:cloud`` suffix separate them — so nothing here is stripped.

    Unifying them has to pick one key, and either choice regresses silently: a
    bare name drops ``LOCAL_PROVIDERS`` and ``_HOSTED_TIER``, sending every
    local small model back to ``lean``; a full id un-anchors ``^claude-haiku-3$``
    and grants a text-only model image support.
    ``test_profile.py::test_profile_and_capability_registries_key_on_different_things``
    pins both halves.
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
