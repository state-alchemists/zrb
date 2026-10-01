"""Fitness function: no emoji a terminal may draw narrower than it is counted.

A variation selector (U+FE0F) turns a narrow symbol (the warning sign, the
pencil, the gear) into an emoji. Many terminals still draw it one column wide
while prompt_toolkit and wcwidth count two, so the letter after it is
overwritten ("⚠️ transcribing" read as "trenscribing"). Emoji that are wide by
default (❗, 📝, 🔧) are counted and drawn alike. Python source is what reaches
a terminal; the web chat's HTML and JavaScript are measured by the browser and
may keep them.
"""

from pathlib import Path

SRC = Path(__file__).parents[2] / "src" / "zrb"


def test_no_python_source_uses_a_variation_selector_emoji():
    offenders = [
        f"{path.relative_to(SRC)}:{number}"
        for path in sorted(SRC.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "️" in line
    ]
    assert not offenders, (
        "Emoji made by a variation selector (U+FE0F) render one column narrow "
        "in many terminals and overlap the next letter; use one that is wide "
        f"by default instead: {offenders}"
    )
