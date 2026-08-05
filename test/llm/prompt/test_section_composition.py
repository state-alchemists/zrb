"""Every subset of sections composes into a prompt that makes sense on its own.

Sections toggle independently via ``LLM_INCLUDE_SECTIONS``, so a cross-reference
is only safe if it disappears with its target. These tests brute-force every
combination rather than spot-checking the default, because the failure mode is a
config nobody tried: a prompt pointing at a section that was never included.
"""

import itertools

import pytest

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


@pytest.mark.parametrize("profile", [None, "mini"])
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


@pytest.mark.parametrize("profile", [None, "mini"])
def test_markers_never_reach_the_model(profile):
    for combo in _subsets():
        text = _compose(set(combo), profile=profile)
        assert "<!--" not in text
        # Marker syntax, not the bare word: "requires" is ordinary English and
        # appears in prose (workflow.md's skill-matching rule). An intact marker
        # is already caught above; these catch a half-stripped one.
        assert "requires:" not in text
        assert "/requires" not in text


@pytest.mark.parametrize("name", FILE_SECTIONS + ["examples.mini"])
def test_every_requires_block_is_closed(name):
    """An unterminated block silently swallows the rest of a section."""
    import re

    text = get_prompt(name)
    assert len(re.findall(r"<!--\s*requires:", text)) == len(
        re.findall(r"<!--\s*/requires\s*-->", text)
    )


def test_mini_examples_are_a_superset_of_the_base():
    """A profile variant replaces the base file, so it must not lose content."""
    base = get_prompt("examples")
    explicit = get_prompt("examples", profile="mini")
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


@pytest.mark.parametrize("profile", [None, "mini"])
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
