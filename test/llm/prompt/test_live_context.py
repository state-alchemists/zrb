"""Tests for the journal-index snapshot injected into ``<live-context>``.

The index is the HUD: it is the only journal file that reaches a session
without anyone searching for it, so what survives truncation is what the
session knows about the user.
"""

from unittest.mock import patch

from zrb.llm.prompt.live_context import render_journal_index


def _write_index(tmp_path, content: str) -> str:
    (tmp_path / "index.md").write_text(content, encoding="utf-8")
    return str(tmp_path)


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
    """A raw slice lands mid-word, leaving a fact as an unreadable fragment."""
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
    # Every surviving entry is a whole line, not a truncated fragment.
    for line in kept:
        assert line.endswith("stated by the user")


def test_head_survives_so_ordering_decides_what_is_kept(tmp_path):
    """Overflow drops from the end — the HUD is written most-durable-first."""
    filler = "\n".join(f"- [insight {i}](technical/n{i}.md)" for i in range(200))
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
    assert "insight 199" not in result


def test_zero_suppresses_the_injection(tmp_path):
    """0 means "max 0 chars", not "unlimited".

    ``EnvField`` falls back to 0 on an unparseable value, so reading 0 as
    unlimited would let a typo'd env var silently uncap the injection.
    """
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    with patch("zrb.llm.prompt.live_context.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = journal_dir
        cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        cfg.LLM_JOURNAL_INDEX_MAX_CHARS = 0

        assert render_journal_index() is None


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
