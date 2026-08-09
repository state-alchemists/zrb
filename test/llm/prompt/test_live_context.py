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


def test_journal_disabled_suppresses_the_injection(tmp_path, monkeypatch):
    """`LLM_JOURNAL_ENABLED=false` wins over a present, non-empty index.

    Callers gate on ``"journal_mandate" in active_sections``, which the switch
    clears — but ``summarize_history`` reaches this directly, so the switch is
    honoured here rather than trusting every call path.
    """
    journal_dir = _write_index(tmp_path, "# Journal\n\n- Name: Go\n")
    monkeypatch.setenv("ZRB_LLM_JOURNAL_DIR", journal_dir)
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "false")

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


# ── Injected context is closed under the preset's tool surface (ADR-0049) ──


class _Ctx:
    """Minimal stand-in for the context ``render_live_context`` reads.

    ``SharedContext.input`` is a read-only property, so the real class cannot
    carry the interactivity flag this needs to steer.
    """

    def __init__(self, interactive: bool):
        self.input = type("_Input", (), {"interactive": interactive, "session": "t"})()


def _live_context(model: str, *, interactive: bool = True) -> str:
    """Render a live-context block as *model*'s preset would receive it."""
    from zrb.llm.prompt.live_context import render_live_context

    return render_live_context(_Ctx(interactive), model, inject_journal_index=True)


def test_a_line_never_names_a_tool_the_preset_dropped():
    """The third channel that can name a tool, and the one nothing guarded.

    ``test_common_tools.py`` closes the docstring channel and
    ``test_section_composition.py`` closes the prompt-section channel. Injected
    context escaped both: ``<live-context>`` announced ``AskUserQuestion`` and
    the journal index announced ``SearchJournal`` on every preset, including the
    two that never register either.
    """
    import re

    from zrb.llm.common_tools import apply_common_tools, tool_name
    from zrb.llm.prompt.profile import active_preset

    registered: set[str] = set()

    class _Host:
        def append_tool(self, *tool):
            registered.update(tool_name(t) for t in tool)

        def append_tool_factory(self, *factory):
            pass

        def append_toolset_factory(self, *factory):
            pass

    apply_common_tools(_Host())
    registered |= {"AskUserQuestion", "SearchJournal", "EnterPlanMode", "ExitPlanMode"}

    for model in ("ollama:llama3.2:3b", "ollama:qwen3:8b", "anthropic:claude-opus-4-8"):
        preset = active_preset(model)
        text = _live_context(model)
        named = {
            n for n in re.findall(r"\b([A-Z][a-zA-Z]+)\b", text) if n in registered
        }
        absent = {n for n in named if not preset.admits(n)}
        assert absent == set(), f"{model}: {sorted(absent)}"


def test_the_non_interactive_line_forbids_no_tool_by_name():
    """Those tools are unregistered in exactly this branch, so naming them is waste.

    ``_resolve_interactive`` gates AskUserQuestion and both plan-mode tools off
    for non-interactive runs, so the sentence spent ~55 tokens per turn warning
    against three tools the model could not see.
    """
    text = _live_context("anthropic:claude-opus-4-8", interactive=False)

    assert "Interactive: no" in text
    for tool in ("AskUserQuestion", "EnterPlanMode", "ExitPlanMode"):
        assert tool not in text
