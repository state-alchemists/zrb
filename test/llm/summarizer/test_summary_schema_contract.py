"""The prompt and the code agree about the snapshot's sections.

`conversational_summarizer.md` is what the model is asked to produce;
`_SUMMARY_SECTIONS` is what the machinery validates, and `_SUMMARY_DROP_ORDER`
is the order in which it gives sections up under cap pressure. The two drifted
silently before: the prompt asked for six sections that restated each other, and
nothing failed when a name was changed in one place only.
"""

import pathlib
import re

from zrb.llm.summarizer.history_summarizer import (
    _SUMMARY_DROP_ORDER,
    _SUMMARY_SECTIONS,
    _is_state_snapshot_well_formed,
)

PROMPT = (
    pathlib.Path(__file__).parents[3]
    / "src"
    / "zrb"
    / "llm"
    / "prompt"
    / "markdown"
    / "conversational_summarizer.md"
)


def _schema_sections() -> list[str]:
    """The tags of the Output Schema block, in the order the prompt writes them."""
    text = PROMPT.read_text(encoding="utf-8")
    schema = text.split("```xml", 1)[1].split("```", 1)[0]
    return re.findall(r"<([a-z_]+)>", schema)


def test_the_prompt_asks_for_exactly_the_sections_the_code_validates():
    sections = _schema_sections()

    assert sections[0] == "state_snapshot"
    assert sections[1:] == list(_SUMMARY_SECTIONS)


def test_every_droppable_section_is_a_real_section():
    for section in _SUMMARY_DROP_ORDER:
        assert section in _SUMMARY_SECTIONS


def test_the_sections_that_resume_the_work_are_never_dropped():
    """Where we are, what was in flight, what comes next and what is unanswered
    are the reason a summary exists; a cap is paid for with the record."""
    for section in ("where_we_are", "now", "next", "open_questions"):
        assert section not in _SUMMARY_DROP_ORDER


def test_a_snapshot_missing_a_section_is_reported():
    complete = (
        "<state_snapshot>"
        + "".join(f"<{section}>x</{section}>" for section in _SUMMARY_SECTIONS)
        + "</state_snapshot>"
    )

    assert _is_state_snapshot_well_formed(complete) is True
    assert _is_state_snapshot_well_formed(complete.replace("<next>x</next>", "")) is False
