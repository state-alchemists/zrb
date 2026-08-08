"""Every subset of sections composes into a prompt that makes sense on its own.

Sections toggle independently via ``LLM_INCLUDE_SECTIONS``, so a cross-reference
is only safe if it disappears with its target. These tests brute-force every
combination rather than spot-checking the default, because the failure mode is a
config nobody tried: a prompt pointing at a section that was never included.
"""

import itertools
import re

import pytest

from zrb.llm.prompt.profile import MINIMAL_SECTIONS, MINIMAL_TOOLS
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.prompt.section_filter import filter_requires

FILE_SECTIONS = [
    "persona",
    "workflow",
    "examples",
]

# Text that must not survive when the section owning it is absent.
#
# Every section is independently switchable, so a section is only correct if it
# reads whole on its own. A pointer at a sibling ("see the Priority Order",
# "per the persona's closing rule") is the failure this catches: it reads fine
# in the default composition and turns into a dangling reference the moment
# someone trims LLM_INCLUDE_SECTIONS. The fix is always to restate the rule
# compactly in place, never to add the pointer back.
OWNED_VOCABULARY = {
    "project_context": ["Documentation Files Found", "User-Level Guidance"],
    # `workflow`'s batching rule withdraws itself for models that cannot batch,
    # which only `system_context` can report. Unguarded, that clause told every
    # trimmed config to consult a section it was never given. Listed here rather
    # than trusted to review: `system_context` is Python-generated, so it is
    # never one of FILE_SECTIONS and the subset walk therefore always asserts
    # this term is absent — exactly the guard the marker has to satisfy.
    "system_context": ["System Context"],
    # `Priority Order` and `Operating Rules` moved here from the retired
    # `mandate` section; the git approval rule moved here from the retired
    # `git_mandate` and is now phrased as `git diff HEAD`.
    "workflow": [
        "Working Loop",
        "Verify Before Done",
        "ActivateSkill",
        "Turn Sequence",
        "When you don't know",
        "Where the deliverable goes",
        "Delegating to sub-agents",
        "Priority Order",
        "Operating Rules",
        "git diff HEAD",
        "Tool usage",
        "Efficiency",
    ],
    "persona": ["Response Calibration"],
}


def _compose(sections: set[str], profile: str | None = None) -> str:
    return "\n".join(
        filter_requires(get_prompt(name, profile=profile), sections)
        for name in sections
        if name in FILE_SECTIONS
    )


def _subsets():
    for size in range(1, len(FILE_SECTIONS) + 1):
        yield from itertools.combinations(FILE_SECTIONS, size)


@pytest.mark.parametrize("profile", [None, "lean"])
def test_no_subset_references_an_absent_section(profile):
    offenders = []
    for combo in _subsets():
        present = set(combo)
        text = _compose(present, profile=profile)
        for owner, vocabulary in OWNED_VOCABULARY.items():
            if owner in present:
                continue
            offenders += [
                (sorted(present), word) for word in vocabulary if word in text
            ]
    assert offenders == []


def test_every_owned_term_still_exists_in_its_owner():
    """A guard for a term nobody says any more guards nothing.

    ``test_no_subset_references_an_absent_section`` asserts a *negative*, so a
    term that has been renamed out of its owner keeps passing while protecting
    the live heading not at all. Both `Cost of guessing wrong` and
    `ActivateSkill` sat here for a release after the text stopped containing
    them. Renaming a heading must now break this test, which is the moment to
    update the map.

    ``project_context`` is skipped: it is assembled in Python, not a file
    ``get_prompt`` can resolve.
    """
    missing = [
        (owner, word)
        for owner, vocabulary in OWNED_VOCABULARY.items()
        if owner in FILE_SECTIONS
        for word in vocabulary
        if word not in get_prompt(owner)
    ]
    assert missing == []


@pytest.mark.parametrize("profile", [None, "lean"])
def test_markers_never_reach_the_model(profile):
    for combo in _subsets():
        text = _compose(set(combo), profile=profile)
        assert "<!--" not in text
        # Marker syntax, not the bare word: "requires" is ordinary English and
        # appears in prose (workflow.md's skill-matching rule). An intact marker
        # is already caught above; these catch a half-stripped one.
        assert "requires:" not in text
        assert "/requires" not in text


@pytest.mark.parametrize("name", FILE_SECTIONS + ["examples.lean"])
def test_every_requires_block_is_closed(name):
    """An unterminated block silently swallows the rest of a section."""
    import re

    text = get_prompt(name)
    assert len(re.findall(r"<!--\s*requires:", text)) == len(
        re.findall(r"<!--\s*/requires\s*-->", text)
    )


def test_lean_examples_are_a_superset_of_the_base():
    """A profile variant replaces the base file, so it must not lose content."""
    base = get_prompt("examples")
    explicit = get_prompt("examples", profile="lean")
    assert explicit.startswith(base.rstrip()[:200])
    assert len(explicit) > len(base)


def test_premise_check_is_first_and_unconditional():
    """The premise check must open the Turn Sequence, unconditionally.

    It is the guard against investigating from an unverified premise — the
    step that must fire before anything else runs. Wrapping it in a
    requires-block or renumbering it behind a conditional step would silently
    drop the guard for some configuration.
    """
    import re

    text = get_prompt("workflow")
    turn = text.split("## Turn Sequence", 1)[1].split("\n## ", 1)[0]
    steps = [
        line.strip()
        for line in turn.splitlines()
        if re.match(r"^\d+\.\s", line.strip())
    ]
    assert steps[0].startswith("1. **Check the premise**")
    assert "<!--requires" not in steps[0]
    assert any("**Activate skills**" in step for step in steps[1:])


@pytest.mark.parametrize("profile", [None, "lean"])
def test_no_numbered_list_gaps_in_any_subset(profile):
    """A conditional item must not leave a hole like `1. 2. 4.` behind.

    A gap reads as "step 3 was withheld from you" — the model has no way to know
    the step does not apply rather than being missing, and a weaker one is more
    likely to stall on it. Conditional items therefore go last in their run.
    """
    import re

    for combo in _subsets():
        text = _compose(set(combo), profile=profile)
        run: list[int] = []
        for line in text.splitlines() + [""]:
            match = re.match(r"^(\d+)\.\s", line.strip())
            if match:
                run.append(int(match.group(1)))
                continue
            if len(run) > 1:
                assert run == list(
                    range(run[0], run[0] + len(run))
                ), f"gap {run} with sections={sorted(combo)}"
            run = []


def test_batching_rule_forbids_the_payload_form():
    """ "Batch twelve edits" must not read as "describe twelve edits".

    A capable model spent 9,193 output tokens printing 44 correct
    ``{path, old_text, new_text}`` objects into its reply and changed no file,
    having read the batching rule as an instruction to assemble one payload.
    `Edit` takes a single replacement by design, so the rule has to say that a
    batch is N calls — otherwise the tool schema and the prompt disagree and the
    model resolves it by writing prose.
    """
    text = get_prompt("workflow")
    section = text.split("### Tool usage", 1)[1].split("\n---", 1)[0]

    assert "Batch independent calls" in section
    assert "N tool calls" in section
    assert "twelve `Edit` calls" in section


def test_default_prompt_stays_within_its_budget():
    """The composed default prompt has a ceiling, enforced.

    Collapsing six rule sections into three took the default composition from
    ~32,600 chars to ~19,500. Nothing stops that creeping back one paragraph at
    a time, so the budget is a test rather than a note. Raising the ceiling is a
    decision to make deliberately, not a diff to wave through.
    """
    from unittest.mock import MagicMock

    from zrb.llm.prompt.manager import PromptManager

    composed = PromptManager().compose_prompt()(MagicMock())
    assert len(composed) < 24_000, f"default prompt grew to {len(composed)} chars"


# ── The safety floor across presets (ADR-0075) ──────────────────────────

# Priority Order rank 1, as three concepts rather than three sentences: each
# entry is the alternative phrasings that count as carrying it. Matching on
# concepts keeps the test from pinning prose, while still failing loudly if a
# lean preset is trimmed until one of the three is simply gone.
RANK_ONE_CONCEPTS = {
    "secrets": [r"secret", r"credential", r"password", r"api key"],
    "tool output is not instructions": [r"data,\s*not", r"ignore\s+\w+\s+instructions"],
    "confirm destructive actions": [r"destructive", r"destroy", r"irreversible"],
}


# (sections, variant) per preset. Only `minimal` constrains the section axis;
# `full` and `lean` compose the default list and differ by variant alone, which
# is why `workflow` is the section name in all three rows.
PRESET_COMPOSITIONS = [
    (["persona", "workflow", "examples"], None),
    (["persona", "workflow", "examples"], "lean"),
    (list(MINIMAL_SECTIONS), "minimal"),
]

# The sections that carry *rules*, weakest-capability last. Each preset reads the
# same two section names and resolves them through its own variant. Examples are
# excluded on purpose: a demonstration lowers burden rather than adding it, so
# the two move in opposite directions (ADR-0047 vs ADR-0075).
RULE_SECTIONS = ["persona", "workflow"]
PRESET_VARIANTS = [("full", None), ("lean", "lean"), ("minimal", "minimal")]


@pytest.mark.parametrize(
    "sections, variant", PRESET_COMPOSITIONS, ids=["full", "lean", "minimal"]
)
def test_every_preset_carries_the_rank_one_safety_rules(sections, variant):
    """Composition may drop method. It may never drop safety.

    `minimal` exists to subtract, so the thing to pin is the floor it may not cut
    through: a preset that trims until secrets, prompt-injection framing, or
    destructive-action confirmation is gone has removed a rule no model class
    can be left without.
    """
    text = "\n".join(
        filter_requires(get_prompt(name, profile=variant), set(sections))
        for name in sections
        if name not in ("system_context", "project_context")
    ).lower()
    missing = [
        concept
        for concept, patterns in RANK_ONE_CONCEPTS.items()
        if not any(re.search(p, text) for p in patterns)
    ]
    assert missing == []


def test_workflow_minimal_names_no_tool_its_preset_lacks():
    """A trimmed preset must not tell the model to call a tool it never gets.

    Same failure as a dangling section pointer, one axis over: `minimal` drops
    most of the tool surface, so its workflow has to route only to what
    survives. Unlike `<!--requires:-->`, nothing strips a stale tool name.
    """
    text = get_prompt("workflow", profile="minimal")
    named = set(re.findall(r"`([A-Z][A-Za-z]+)`", text))
    assert named <= MINIMAL_TOOLS, sorted(named - MINIMAL_TOOLS)


def test_every_variant_resolves_to_its_own_file():
    """A missing variant falls back silently, so the fallback must be pinned.

    `get_prompt` returning the base file on a typo is the right runtime
    behaviour and the wrong test outcome: every burden assertion below would
    compare `workflow.md` against itself and pass.
    """
    base = get_prompt("workflow")
    for _, variant in PRESET_VARIANTS:
        if variant is None:
            continue
        assert get_prompt("workflow", profile=variant) != base, variant
    assert get_prompt("examples", profile="lean") != get_prompt("examples")


def test_rule_burden_falls_as_the_target_model_gets_weaker():
    """The less capable the model, the less we ask it to hold at once.

    The ordering is the whole point of having presets: `lean` used to be the
    *heaviest* composition in the system, shipping a 7B model the frontier
    rulebook plus 1,200 extra tokens of examples.

    Mass and rule count must fall strictly — those are the load itself. Clause
    nesting only has to not *rise*: it is a style proxy with a floor, and both
    lighter rulebooks already sit on it, so demanding a strict drop there would
    force prose damage to satisfy a number. Examples are excluded from all three
    measures on purpose — a demonstration lowers burden rather than adding it,
    so it moves opposite the rules (ADR-0047 vs ADR-0075).
    """
    measured = []
    for preset, variant in PRESET_VARIANTS:
        text = "\n".join(get_prompt(name, profile=variant) for name in RULE_SECTIONS)
        measured.append(
            (
                preset,
                len(text),
                len(re.findall(r"^\s*[-*\d]+[.)]?\s+", text, re.M)),
                len(re.findall(r"[—;(]", text)),
            )
        )
    for (lo_name, *lo), (hi_name, *hi) in zip(measured, measured[1:]):
        for label, a, b in zip(("chars", "rules"), lo, hi):
            assert b < a, f"{label}: {hi_name}={b} is not below {lo_name}={a}"
        assert (
            hi[2] <= lo[2]
        ), f"subclauses: {hi_name}={hi[2]} rose above {lo_name}={lo[2]}"


def test_workflow_lean_names_no_tool_that_does_not_exist():
    """Same guard as `workflow.minimal.md`, against the full tool surface.

    `lean` keeps every tool, so the risk is not a trimmed surface but a stale
    name: nothing strips a tool reference that no longer resolves.
    """
    from zrb.llm.common_tools import apply_common_tools, tool_name

    registered: set[str] = set()

    class _Host:
        def add_tool(self, *tool):
            registered.update(tool_name(t) for t in tool)

        def add_tool_factory(self, *factory):
            pass

        def add_toolset_factory(self, *factory):
            pass

    apply_common_tools(_Host())
    # Factory-built and main-agent-only tools are not enumerable without a
    # context or a chat task. Name the ones the prompt cites, so a rename to any
    # of them still fails this test.
    registered |= {
        "ActivateSkill",
        "AskUserQuestion",
        "EnterPlanMode",
        "DelegateToAgent",
    }
    named = set(
        re.findall(r"`([A-Z][A-Za-z]+)`", get_prompt("workflow", profile="lean"))
    )
    assert named <= registered, sorted(named - registered)
