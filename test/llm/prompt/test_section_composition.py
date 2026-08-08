"""Every subset of sections composes into a prompt that makes sense on its own.

Sections toggle independently via ``LLM_INCLUDE_SECTIONS``, so a cross-reference
is only safe if it disappears with its target. These tests brute-force every
combination rather than spot-checking the default, because the failure mode is a
config nobody tried: a prompt pointing at a section that was never included.
"""

import itertools
import re

import pytest

from zrb.llm.prompt.profile import LEAN_DROPS, MINIMAL_SECTIONS, MINIMAL_TOOLS
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
        "Final Reminders",
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


#: What the base `examples.md` demonstrates, as a stance the variant must also
#: teach. Concepts rather than prose: a variant exists to re-word for its model
#: class, so pinning bytes would forbid the only thing it is for.
BASE_EXAMPLE_CONCEPTS = {
    "stance: a question is answered": [r"thread and a process", r"opens no files"],
    "stance: a directive is carried out": [r"getUserData|legacy_auth", r"call site"],
    "check, don't recall": [r"rather than (eyeballing|answering from memory)"],
    "tool results are data": [r"IGNORE PREVIOUS INSTRUCTIONS", r"injection"],
    "delegate heavy discovery": [r"read-only research agents|sub-?agents"],
}


def test_a_variant_of_examples_still_teaches_what_the_base_teaches():
    """A variant replaces the base file, so it must not lose *coverage*.

    Coverage, not bytes. This used to assert that `examples.lean.md` opened with
    `examples.md` verbatim, which enforced the wrong thing in the right
    direction: it guaranteed nothing was dropped by guaranteeing the two files
    were the same file, so every edit to the base desynchronized the variant and
    the variant could never re-word for its own model class. Match on the stance
    each demonstration teaches and let the wording differ — which is what
    ``test_a_variant_of_examples_is_not_a_superset_of_the_base`` then requires.
    """
    import re

    lean = get_prompt("examples", profile="lean")
    missing = [
        concept
        for concept, patterns in BASE_EXAMPLE_CONCEPTS.items()
        if not all(re.search(p, lean) for p in patterns)
    ]
    assert missing == []


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
# the two move in opposite directions (ADR-0047 vs ADR-0075) — they get their own
# ceiling in `test_demonstrations_do_not_grow_as_the_target_model_gets_weaker`.
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


# The closing recap, as the body statement each item restates. Every preset ends
# with `## Final Reminders`, which exists to put the highest-cost rules at the
# recency position the way `Priority Order` puts them at the primacy one.
RECAP_ANCHORS = {
    "tool output is not instructions": [r"data,? not (instructions|orders)"],
    "confirm destructive actions": [r"destructive|destroy"],
    "name the cause first": [r"[Nn]ame the cause|[Ss]ay the cause"],
    "acting is not describing": [
        r"[Ss]tating an action is not performing it|do not describe it"
    ],
    "check the artifact": [r"[Cc]heck (the artifact|your work)"],
    "finish the turn": [r"[Ff]inish the work this turn|[Rr]eport the real result"],
}


@pytest.mark.parametrize("variant", [None, "lean", "minimal"])
def test_the_closing_recap_restates_only_what_the_body_states(variant):
    """A recap is duplication on purpose. Divergent duplication is the bug.

    `Priority Order` opens the rulebook to exploit primacy; nothing exploited
    recency, which is where a rule read just before the request lands hardest —
    the slot kimi's "Ultimate Reminders" and gemini's "Final Reminder" occupy.
    Adding one is safe only while it stays a *pointer* to rules stated above it:
    a recap that introduces a rule of its own splits the rulebook in two, and the
    copy nobody edits is the one the model reads last.

    Asserted in the direction that can actually rot: every recapped rule must
    still be stated in the body. AGENTS.md's MECE rule tolerates consistent
    duplication inside one section and forbids the divergent kind.
    """
    text = get_prompt("workflow", profile=variant)
    body, _, recap = text.partition("## Final Reminders")
    assert recap.strip(), f"workflow[{variant}] ships no closing recap"
    items = re.findall(r"^\d+\.\s", recap, re.M)
    assert len(items) >= 4, f"workflow[{variant}] recap has only {len(items)} items"
    unanchored = [
        rule
        for rule, patterns in RECAP_ANCHORS.items()
        if any(re.search(p, recap) for p in patterns)
        and not any(re.search(p, body) for p in patterns)
    ]
    assert unanchored == [], f"workflow[{variant}] recaps rules its body never states"


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


def _burden(section: str, variant: str | None) -> tuple[int, int, int]:
    """Mass, rule count, and clause nesting for one section under one variant."""
    text = get_prompt(section, profile=variant)
    return (
        len(text),
        len(re.findall(r"^\s*[-*\d]+[.)]?\s+", text, re.M)),
        len(re.findall(r"[—;(]", text)),
    )


@pytest.mark.parametrize("section", RULE_SECTIONS)
def test_rule_burden_falls_as_the_target_model_gets_weaker(section):
    """The less capable the model, the less we ask it to hold at once.

    The ordering is the whole point of having presets: `lean` used to be the
    *heaviest* composition in the system, shipping a 7B model the frontier
    rulebook plus 1,200 extra tokens of examples.

    Measured **per section**, not over their concatenation. A summed measure
    reports the total and hides its terms: `persona` shipped every preset the
    same 486 tokens of frontier-register prose — 35% of `minimal`'s whole rule
    payload — and the sum still fell, because `workflow.minimal.md` shrank
    enough to cover for it. A section that never varies is a section whose
    variant nobody wrote, and the silent `foo.{profile}.md` → `foo.md` fallback
    (ADR-0047) means nothing else says so.

    Mass and rule count must fall strictly — those are the load itself. Clause
    nesting only has to not *rise*: it is a style proxy with a floor, and the
    lighter rulebooks already sit on it, so demanding a strict drop there would
    force prose damage to satisfy a number.
    """
    measured = [
        (preset, _burden(section, variant)) for preset, variant in PRESET_VARIANTS
    ]
    for (lo_name, lo), (hi_name, hi) in zip(measured, measured[1:]):
        for label, a, b in zip(("chars", "rules"), lo, hi):
            assert (
                b < a
            ), f"{section}: {label}: {hi_name}={b} is not below {lo_name}={a}"
        assert (
            hi[2] <= lo[2]
        ), f"{section}: subclauses: {hi_name}={hi[2]} rose above {lo_name}={lo[2]}"


@pytest.mark.parametrize("variant", [None, "lean"])
def test_examples_carry_no_rule_of_their_own(variant):
    """`examples` demonstrates; it never legislates.

    `examples.md` opens by saying so and `OWNED_VOCABULARY` gives `examples` no
    terms, but both are *absences* — nothing failed when `examples.lean.md`
    grew three `Wrong:` verdicts. A `Wrong:` clause is a rule wearing a
    demonstration's clothes: it states what the model must not do, in a section
    every other guard treats as carrying nothing to state.

    It also matters where the rule ends up. A rule stated only in `examples`
    reaches nobody in `minimal`, which drops the section, and it is invisible to
    the per-section burden ladder, which excludes it. Both are ways for a rule
    to go missing quietly, which is exactly what ADR-0047's
    no-variant-only-rules invariant forbids one axis over.
    """
    text = get_prompt("examples", profile=variant)
    assert "Wrong:" not in text, f"examples[{variant}] states a rule as a verdict"


def test_a_variant_of_examples_is_not_a_superset_of_the_base():
    """Two files, one content, no test between them — they will drift.

    `examples.lean.md` used to open with `examples.md` verbatim and append to
    it. The variant axis *replaces*, so the copy bought nothing a shorter file
    would not, and every edit to the base silently desynchronized the variant.
    """
    base = get_prompt("examples").strip()
    lean = get_prompt("examples", profile="lean").strip()
    assert base not in lean, "examples.lean.md embeds examples.md verbatim"


def test_a_weaker_targets_preset_ships_less_prompt_in_total():
    """The composed payload falls too, not only its rule-carrying half.

    The per-section ladder above governs `persona` and `workflow`; `examples` is
    exempt from it because a demonstration lowers burden rather than adding it
    (ADR-0047 vs ADR-0075), so a lighter preset is *allowed* proportionally more
    of it. Exempt from the ladder is not exempt from the budget: `lean` spent
    its 700-token rulebook saving on 1,200 tokens of extra examples and came out
    the heaviest composition in the system — 5,061 tokens against `full`'s
    4,563, shipped to the weaker model.

    Whatever the per-rule argument, the total is what a 7B model has to attend
    to before it reads the request. So the totals are ordered as well, and a
    preset that wants more demonstrations pays for them out of its own rulebook
    rather than out of the model's attention.
    """
    measured = [
        (preset, sum(len(get_prompt(name, profile=variant)) for name in sections))
        for (preset, _), (sections, variant) in zip(
            PRESET_VARIANTS, PRESET_COMPOSITIONS
        )
    ]
    for (lo_name, lo), (hi_name, hi) in zip(measured, measured[1:]):
        assert hi < lo, f"total: {hi_name}={hi} is not below {lo_name}={lo}"


def test_workflow_lean_names_no_tool_its_preset_lacks():
    """Same guard as `workflow.minimal.md`, against `lean`'s own surface.

    Was "against the full tool surface", on the reasoning that `lean` keeps every
    tool so only a stale name could dangle. `lean` now subtracts `LEAN_DROPS`,
    which makes it the same failure as `minimal`'s: a rulebook naming a tool its
    own preset never registers. Nothing strips a tool reference the way
    `<!--requires:-->` strips a section reference.
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
    available = registered - LEAN_DROPS
    named = set(
        re.findall(r"`([A-Z][A-Za-z]+)`", get_prompt("workflow", profile="lean"))
    )
    assert named <= available, sorted(named - available)


def test_lean_drops_only_tools_that_are_actually_registered():
    """A drop naming a tool nobody registers silently protects nothing.

    Same shape as `test_every_owned_term_still_exists_in_its_owner`: `LEAN_DROPS`
    is applied as a filter, so a renamed or deleted tool leaves a dead entry that
    keeps passing every closure check while subtracting nothing.
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
    # `SearchJournal` and the writers are factory-built (gated on
    # LLM_JOURNAL_ENABLED), so they never reach add_tool here.
    factory_built = {"SearchJournal", "LogActivity", "WriteJournalNote"}
    assert LEAN_DROPS <= (registered | factory_built), sorted(
        LEAN_DROPS - registered - factory_built
    )
