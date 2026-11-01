"""What the cap keeps when the journal index does not fit.

The index is the only journal file injected unprompted, so these tests are about
one trade: the block has to carry the claims that hold every turn, and a section
that happens to be long must not be the reason a shorter one arrives empty.
"""

from zrb.llm.prompt.journal_core import join_overflow, plan_index_core

PIN = "📌 "
MORE = "(...more)"


def _claim(text: str, slug: str, category: str = "technical", pinned: bool = False):
    mark = PIN if pinned else ""
    return f"- {mark}{text} ([note]({category}/{slug}.md))"


def _title(text: str, path: str) -> str:
    return f"- [{text}]({path})"


def _index(*sections: tuple[str, list[str]]) -> str:
    """An index shaped the way the writers render one."""
    parts = ["# Journal"]
    for heading, lines in sections:
        parts.append(f"## {heading}")
        parts.append("")
        parts.extend(lines)
    return "\n".join(parts) + "\n"


def test_an_index_that_fits_is_returned_untouched():
    content = _index(("User", [_claim("Name: Go.", "name-go", "user")]))
    kept, note = plan_index_core(content, len(content))
    assert kept == content
    assert note == ""


def test_a_pinned_line_outranks_a_claim_that_fits_easier():
    """A pin is a note that said it holds every turn: it is the one line whose
    loss changes an answer instead of delaying one, so it goes in first even
    when the claim beside it is shorter."""
    content = _index(
        ("User", [_claim("x" * 200, "long"), _claim("short pin", "pin", pinned=True)]),
    )
    kept, _ = plan_index_core(content, 120)
    assert "short pin" in kept
    assert "x" * 200 not in kept


def test_a_long_section_does_not_empty_a_short_one():
    """The failure this module exists for: the head-first cut spent the whole cap
    on `## User` and left every section below it empty, pinned lines included."""
    filler = [_title(f"insight {i}", f"technical/n{i}.md") for i in range(60)]
    content = _index(("User", [_claim("Name: Go.", "name-go", "user")]), ("Recent", filler))
    kept, _ = plan_index_core(content, 500)
    assert "## User" in kept
    assert "Name: Go." in kept
    assert "## Recent" in kept


def test_a_claim_outranks_the_pointer_to_the_category_indexes():
    """The block's header already says each category's own index lists every note
    in it, so the `## Directories` line is the cheap thing to lose — a claim is
    not, because it is the only place that fact is stated at all."""
    claims = [_claim(f"a claim worth keeping {i}", f"claim-{i}") for i in range(8)]
    content = _index(
        ("Recent", claims),
        ("Directories", ["- [user](user/index.md) · [technical](technical/index.md)"]),
    )
    kept, _ = plan_index_core(content, 200)
    assert "a claim worth keeping 0" in kept
    assert "[user](user/index.md)" not in kept


def test_a_title_whose_note_already_shows_as_a_claim_is_dropped():
    """The same fact twice, the second time weaker, is what made the catalog a
    quarter of the index. A title for a note with no claim stays: it is the only
    trace that note has."""
    titles = [
        _title("Something with no claim", "technical/lonely.md"),
        _title("A claim about retries", "technical/retries.md"),
        *(_title(f"other {i}", f"technical/o{i}.md") for i in range(40)),
    ]
    content = _index(
        ("Recent", [_claim("A claim about retries.", "retries")]),
        ("Recent Insights", titles),
    )
    kept, _ = plan_index_core(content, 1_000)
    assert "A claim about retries." in kept
    assert _title("Something with no claim", "technical/lonely.md") in kept
    assert _title("A claim about retries", "technical/retries.md") not in kept


def test_a_duplicate_title_is_not_reported_as_hidden():
    """Nothing was withheld by dropping it — the claim that says the same thing
    is in the block — so calling it hidden would send the model looking for a
    fact it already has."""
    content = _index(
        ("Recent", [_claim("A claim about retries.", "retries")]),
        ("Recent Insights", [_title("A claim about retries", "technical/retries.md")]),
    )
    kept, note = plan_index_core(content, 120)
    assert "A claim about retries." in kept
    assert note == "(...more)"


def test_the_note_names_the_section_that_lost_lines():
    """A section name is what tells the model whether the missing part matters;
    a bare count of notes reads as 'nothing important'."""
    filler = [_claim(f"headline {i} with a little length", f"n{i}") for i in range(60)]
    content = _index(("Recent", filler))
    _, note = plan_index_core(content, 2_000)
    assert note.startswith("- Hidden ")
    assert "under ## Recent" in note
    assert note.endswith("(...more)")


def test_the_note_counts_the_pinned_lines_that_did_not_fit():
    pins = [_claim(f"constraint {i} " * 4, f"c{i}", pinned=True) for i in range(10)]
    content = _index(("Constraints", pins))
    _, note = plan_index_core(content, 500)
    assert "pinned lines did not fit" in note


def test_a_note_never_costs_a_claim():
    """The body is filled against a cap already reduced by the note's share, so a
    sentence about what is missing is never paid for with a claim. Room the body
    could not use then goes to the note — which is why the same content names a
    section at 150 and can only afford the bare marker at 120."""
    filler = [_claim(f"filler {i} " * 3, f"f{i}") for i in range(10)]
    content = _index(("Recent", [_claim("a claim worth keeping", "kept"), *filler]))
    bare, note = plan_index_core(content, 120)
    assert "a claim worth keeping" in bare
    assert note == "(...more)"
    named, note = plan_index_core(content, 150)
    assert "a claim worth keeping" in named
    assert "under ## Recent" in note


def test_the_budget_bounds_the_kept_text_and_the_note():
    """The old cap took a slice and then appended the summary on top, so a
    2,500-char cap produced a 4,049-char block. A cap that exempts the text
    standing in for what it dropped is not a cap."""
    filler = [_claim(f"claim number {i} with some length to it", f"n{i}") for i in range(50)]
    content = _index(("Recent", filler))
    for budget in (150, 300, 900, 2_000):
        kept, note = plan_index_core(content, budget)
        assert len(kept) + 1 + len(note) <= budget, budget


def test_no_heading_is_emitted_over_an_empty_section():
    """A blank line in a section is not a candidate: letting one compete opened
    the heading and then kept nothing under it."""
    content = _index(
        ("User", [_claim("kept claim", "kept")]),
        ("Agent", [_claim("x" * 400, "huge")]),
    )
    kept, _ = plan_index_core(content, 120)
    assert "## User" in kept
    assert "## Agent" not in kept


def test_a_bullet_index_without_headings_is_trimmed_too():
    """A journal written before the HUD sections existed has bullets and no
    headings; it still has to fit, and still has to cut on a line boundary."""
    lines = [f"- preference number {i} stated by the user" for i in range(50)]
    content = "# Journal\n" + "\n".join(lines) + "\n"
    kept, note = plan_index_core(content, 200)
    assert kept.startswith("# Journal")
    assert "preference number 0 stated by the user" in kept
    assert "preference number 49" not in kept
    assert note.endswith("(...more)")
    for line in kept.splitlines():
        assert not line.startswith("- preference") or line.endswith("stated by the user")


def test_a_hand_written_line_that_links_a_claimed_note_is_not_a_duplicate():
    """Only a catalog entry restates a claim. A hand-written line inside a HUD
    section is user content that exists nowhere else, so it is not suppressed for
    naming a note whose claim is already in the block (review on #791)."""
    titles = [_title(f"other {i}", f"technical/o{i}.md") for i in range(30)]
    content = _index(
        (
            "User",
            [
                _claim("Name: Go.", "x", "user"),
                "- See [details](user/x.md) for the rest",
            ],
        ),
        ("Recent Insights", [_title("Name: Go", "user/x.md"), *titles]),
    )
    kept, _ = plan_index_core(content, 800)
    assert "- See [details](user/x.md) for the rest" in kept
    assert _title("Name: Go", "user/x.md") not in kept


def test_a_cap_below_the_marker_injects_nothing():
    """The marker is ten characters including its newline. Under that, there is
    nothing honest to return — returning the marker anyway spends more than the
    cap it is supposed to stay inside (review on #791)."""
    content = _index(("Recent", [_claim("x" * 200, "long")]))
    for budget in (1, 5, 9):
        kept, note = plan_index_core(content, budget)
        assert len(kept) + len(note) <= budget, budget


def test_a_title_is_kept_when_its_claim_did_not_fit():
    """Suppressing a title because *some* claim names the same note is only right
    when that claim reached the block. Otherwise a long pin that does not fit
    takes the note's only remaining trace with it (review on #791)."""
    content = _index(
        ("Recent", [_claim("a very long claim " * 12, "long", pinned=True)]),
        ("Recent Insights", [_title("Short title", "technical/long.md")]),
    )
    kept, _ = plan_index_core(content, 200)
    assert "a very long claim" not in kept
    assert _title("Short title", "technical/long.md") in kept


def test_an_oversized_preamble_is_trimmed_like_a_section():
    """The lines above the first heading are part of the index too. Charging them
    to the budget without being able to drop one returned more than the cap
    whenever the preamble was bigger than it — 337 characters for a 10-character
    budget, found in review on #791."""
    lines = [f"- hand-written line {i} above every heading" for i in range(30)]
    content = "# Journal\n" + "\n".join(lines) + "\n\n## User\n\n- Name: Go\n"
    for budget in (10, 60, 300):
        kept, note = plan_index_core(content, budget)
        assert len(kept) + 1 + len(note) <= budget, budget
    kept, note = plan_index_core(content, 300)
    assert "hand-written line 0" in kept
    assert "hand-written line 29" not in kept
    assert "at the top of the file" in note


def test_a_zero_budget_is_the_callers_decision_not_this_modules():
    content = _index(("User", [_claim("Name: Go.", "name-go", "user")]))
    assert plan_index_core(content, 0) == (content, "")


def _shapes() -> dict[str, str]:
    """Indices shaped for the edges, one per finding review raised on #791.

    The four findings were a preamble bigger than the cap, a claim too long to
    fit, a catalog line that was not a catalog entry, and a cap below the marker.
    Each shape below makes one of those the ordinary case rather than the corner."""
    return {
        "empty": "",
        "title alone": "# Journal\n",
        "preamble only": "# Journal\n\n"
        + "\n".join(f"- hand-written line {i} above every heading" for i in range(20))
        + "\n",
        "one oversized line": "# Journal\n\n## Recent\n\n" + _claim("x" * 400, "huge") + "\n",
        "no headings at all": "# Journal\n\n"
        + "\n".join(f"- preference number {i} stated by the user" for i in range(40))
        + "\n",
        "catalog heavy": _index(
            ("Recent", [_claim("A claim about retries.", "retries")]),
            (
                "Recent Insights",
                [_title(f"note {i}", f"technical/n{i}.md") for i in range(30)],
            ),
        ),
        "pin heavy": _index(
            (
                "Constraints",
                [_claim(f"constraint {i} that holds", f"c{i}", pinned=True) for i in range(15)],
            ),
        ),
        "a hand-written line beside a claim": _index(
            (
                "User",
                [_claim("Name: Go.", "x", "user"), "- See [details](user/x.md) for the rest"],
            ),
            ("Recent Insights", [_title("Name: Go", "user/x.md")]),
        ),
        "the real shape": _index(
            ("User", [_claim(f"a preference the user stated, number {i}", f"p{i}") for i in range(20)]),
            ("Constraints", [_claim("Never push to main", "c1", pinned=True)]),
            ("Agent", []),
            ("Recent", [_claim(f"headline {i}", f"h{i}") for i in range(10)]),
            ("Directories", ["- [user](user/index.md) · [technical](technical/index.md)"]),
        ),
    }


def _budgets(content: str) -> list[int]:
    """Every small cap, where the marker and the first section straddle a boundary,
    then a spread up to the index's own length."""
    step = max(1, len(content) // 12)
    return sorted(
        {
            *range(1, min(len(content), 160) + 1),
            *range(160, len(content) + 1, step),
            len(content),
        }
    )


def test_the_cap_holds_on_every_edge_of_every_shape():
    """The four findings review raised on #791 were all boundaries — a preamble
    bigger than the cap, a claim too long to fit, a cap below the marker — and the
    suite was green through all of them because every test sat in the middle of
    the range. This walks the boundaries instead: nine adversarial indices crossed
    with every small cap and a spread up to the index's own length.

    Four statements are checked at each point, and they are the module's contract
    rather than its shape: the cap holds, a truncated block says it is truncated,
    nothing is emitted that is not a whole line of the index, and no heading stands
    over an empty section."""
    for name, content in _shapes().items():
        source = set(content.splitlines())
        for budget in _budgets(content):
            kept, note = plan_index_core(content, budget)
            assert len(join_overflow(kept, note)) <= budget, (name, budget)
            if budget >= len(content):
                assert (kept, note) == (content, ""), (name, budget)
            if kept and len(content) > budget:
                assert note.endswith(MORE), (name, budget, note)
            plainly_fits = any(len(line) + 40 <= budget for line in source)
            if plainly_fits and len(content) > budget:
                assert kept, (name, budget, "a line that plainly fits was not kept")
            lines = kept.splitlines()
            assert set(lines) <= source, (name, budget, set(lines) - source)
            for index, line in enumerate(lines):
                if line.startswith("## "):
                    assert index + 1 < len(lines), (name, budget, line)
                    assert not lines[index + 1].startswith("## "), (name, budget, line)
