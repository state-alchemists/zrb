"""Every subset of sections composes into a prompt that makes sense on its own.

Sections toggle independently via ``LLM_INCLUDE_SECTIONS``, so a cross-reference
is only safe if it disappears with its target. These tests brute-force every
combination rather than spot-checking the default, because the failure mode is a
config nobody tried: a prompt telling the model to search a journal that was
never included.
"""

import itertools

import pytest

from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.prompt.section_filter import filter_requires

FILE_SECTIONS = [
    "persona",
    "mandate",
    "workflow",
    "examples",
    "git_mandate",
    "journal_mandate",
]

# Text that must not survive when the section owning it is absent.
OWNED_VOCABULARY = {
    "journal_mandate": ["journal", "Journal", "SearchJournal"],
    "project_context": ["Documentation Files Found", "User-Level Guidance"],
    "workflow": ["Working Loop", "Verify Before Done", "ActivateSkill"],
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
