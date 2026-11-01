"Tests for the journal index injected into ``<live-context>``."

from unittest.mock import patch

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.live_context import render_journal_index


def _write_index(tmp_path, content: str) -> str:
    (tmp_path / "index.md").write_text(content, encoding="utf-8")
    return str(tmp_path)


def test_the_injected_index_is_the_configured_filename(tmp_path):
    """The writers name every index from `LLM_JOURNAL_INDEX_FILE`, so the reader
    must resolve the same knob — and say the same name to the model, which
    otherwise looks for `index.md` in a category that has none."""
    (tmp_path / "notes-index.md").write_text(
        "# Journal\n\n- Name: Go\n", encoding="utf-8"
    )
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = str(tmp_path)
        cfg.LLM_JOURNAL_INDEX_FILE = "notes-index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500

        result = render_journal_index()

    assert result is not None
    assert "- Name: Go" in result
    assert "a category's notes-index.md" in result
    assert "technical/notes-index.md" in result


def test_returns_none_for_a_traversal_index_name(tmp_path):
    """`LLM_JOURNAL_INDEX_FILE` is config, not a sandboxed value — a path like
    `../../secrets.md` must never be joined under the journal directory and
    injected into the prompt, same as the writers already refuse it."""
    journal_dir = tmp_path / "notes"
    journal_dir.mkdir()
    secret = tmp_path / "secrets.md"
    secret.write_text("sk-super-secret\n", encoding="utf-8")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = str(journal_dir)
        cfg.LLM_JOURNAL_INDEX_FILE = "../secrets.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500

        assert render_journal_index() is None


def test_returns_none_for_an_absolute_index_name(tmp_path):
    journal_dir = tmp_path / "notes"
    journal_dir.mkdir()
    secret = tmp_path / "secrets.md"
    secret.write_text("sk-super-secret\n", encoding="utf-8")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = str(journal_dir)
        cfg.LLM_JOURNAL_INDEX_FILE = str(secret)
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500

        assert render_journal_index() is None


def test_returns_none_when_index_is_missing(tmp_path):
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = str(tmp_path)
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500

        assert render_journal_index() is None


def test_short_index_is_injected_whole(tmp_path):
    journal_dir = _write_index(tmp_path, "# Journal\n\n## User\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500

        result = render_journal_index()

    assert result is not None
    assert "- Name: Go" in result
    assert "(...more)" not in result


def test_overflow_is_cut_on_a_line_boundary(tmp_path):
    "A raw slice lands mid-word, leaving a fact as an unreadable fragment."
    lines = [f"- preference number {i} stated by the user" for i in range(200)]
    journal_dir = _write_index(tmp_path, "# Journal\n" + "\n".join(lines) + "\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 500

        result = render_journal_index()

    assert result is not None
    assert "(...more)" in result
    body = result.split("</journal-index>")[0]
    kept = [ln for ln in body.splitlines() if ln.startswith("- preference")]
    assert kept, "expected at least one surviving entry"

    for line in kept:
        assert line.endswith("stated by the user")


def test_a_short_section_survives_a_long_one(tmp_path):
    """The cap is spent across sections, not from the top: a section that happens
    to come first must not be the reason the one below it arrives empty."""
    filler = "\n".join(
        f"- [insight {i}](technical/n{i}.md)" for i in reversed(range(200))
    )
    journal_dir = _write_index(
        tmp_path, f"# Journal\n\n## User\n\n- Name: Go\n\n## Recent\n\n{filler}\n"
    )
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 400

        result = render_journal_index()

    assert result is not None
    assert "- Name: Go" in result
    assert "## Recent" in result
    # A section renders newest first, so what survives is its newest entries.
    assert "- [insight 199]" in result
    assert "- [insight 0]" not in result


def test_the_overflow_note_names_the_section_that_lost_lines(tmp_path):
    """A cap that empties a section must say which one: '(...more)' alone reads as
    'nothing important', and the model re-derives what is already recorded."""
    filler = "\n".join(f"- [tech {i}](technical/n{i}.md)" for i in reversed(range(40)))
    journal_dir = _write_index(
        tmp_path,
        "# Journal\n\n## User\n\n- Name: Go\n\n"
        f"## Recent\n\n{filler}\n\n## Agent\n\n- [who](agent/who.md)\n",
    )
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 400

        result = render_journal_index()

    assert result is not None
    assert "under ## Recent" in result
    assert "(...more)" in result


def test_zero_suppresses_the_injection(tmp_path):
    "Zero suppresses injection rather than disabling the limit."
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 0

        assert render_journal_index() is None


def test_a_cap_with_no_room_for_a_line_injects_nothing(tmp_path):
    """The wrapper is instruction, not journal. Under a cap too small to carry one
    line of the index the block would arrive with nothing under a sentence saying
    what to search — 566 characters of prompt to say nothing, measured on the real
    index with the cap at 9 (review on #791). The cap is meant to bound what the
    index costs, so a cap that cannot pay for any of it pays for none."""
    filler = "\n".join(f"- preference number {i} stated by the user" for i in range(50))
    journal_dir = _write_index(tmp_path, f"# Journal\n\n{filler}\n")
    for cap in (1, 5, 9):
        with patch("zrb.llm.prompt.live_context.CFG") as cfg:
            cfg.LLM_JOURNAL_DIR = journal_dir
            cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
            cfg.LLM_JOURNAL_INDEX_MAX_CHARS = cap

            assert render_journal_index() is None, cap


def test_journal_disabled_suppresses_the_injection(tmp_path, monkeypatch):
    "The disabled setting suppresses injection."
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    monkeypatch.setenv("ZRB_LLM_JOURNAL_DIR", journal_dir)
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "false")

    assert render_journal_index() is None


def test_footer_points_at_the_uncapped_category_catalog(tmp_path):
    "The footer points to the uncapped category index."
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500

        result = render_journal_index()

    assert result is not None
    assert "index.md" in result
    assert "uncapped" in result


def test_header_routes_journal_changes_through_the_writer_tools(tmp_path):
    "The header directs journal changes through writer tools."
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500

        result = render_journal_index()

    assert result is not None
    for tool in ("LogActivity", "WriteJournalNote", "DeleteJournalNote"):
        assert tool in result
    assert "Search for these tools" in result


def test_auto_search_adds_a_separate_unverified_section(tmp_path):
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500
        cfg.LLM_JOURNAL_AUTO_SEARCH_ENABLED = True
        cfg.LLM_JOURNAL_AUTO_SEARCH_MAX_HITS = 3
        with patch(
            "zrb.llm.tool.journal.find_in_journal",
            return_value={
                "summary": "Found 1 matches.",
                "results": [
                    {"file": "technical/retry.md", "line": "3", "content": "retries"}
                ],
            },
        ):
            result = render_journal_index(first_message="tell me about retries")

    assert result is not None
    assert "## Possibly Related" in result
    assert "unverified" in result
    assert "technical/retry.md" in result


def test_auto_search_omitted_when_disabled(tmp_path):
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500
        cfg.LLM_JOURNAL_AUTO_SEARCH_ENABLED = False

        result = render_journal_index(first_message="tell me about retries")

    assert result is not None
    assert "## Possibly Related" not in result


def test_auto_search_omitted_on_zero_hits(tmp_path):
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 2500
        cfg.LLM_JOURNAL_AUTO_SEARCH_ENABLED = True
        cfg.LLM_JOURNAL_AUTO_SEARCH_MAX_HITS = 3
        with patch(
            "zrb.llm.tool.journal.find_in_journal",
            return_value={"summary": "No matches found.", "results": []},
        ):
            result = render_journal_index(first_message="xyzzy_no_match")

    assert result is not None
    assert "## Possibly Related" not in result


def test_negative_injects_the_whole_index_uncapped(tmp_path):
    filler = "\n".join(f"- [insight {i}](technical/n{i}.md)" for i in range(200))
    journal_dir = _write_index(tmp_path, f"# Journal\n\n{filler}\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = -1

        result = render_journal_index()

    assert result is not None
    assert "insight 199" in result
    assert "(...more)" not in result


def _ctx(interactive: bool) -> Context:
    "A real task context carrying the interactivity flag the render reads."
    shared_ctx = SharedContext(input={"interactive": interactive, "session": "t"})
    return Context(shared_ctx, "test", 0, "")


def _live_context(model: str, *, interactive: bool = True) -> str:
    "Render a live-context block as *model*'s preset would receive it."
    from zrb.llm.prompt.live_context import render_live_context

    return render_live_context(_ctx(interactive), model, inject_journal_index=True)


def test_the_non_interactive_line_forbids_no_tool_by_name():
    "Those tools are unregistered in exactly this branch, so naming them is waste."
    text = _live_context("anthropic:claude-opus-4-8", interactive=False)

    assert "Interactive: no" in text

    guard = next(
        line for line in text.splitlines() if line.startswith("- Interactive:")
    )
    for tool in ("AskUserQuestion", "EnterPlanMode", "ExitPlanMode"):
        assert tool not in guard
