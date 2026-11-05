"""Pointer chains: when a `@path` file is followed, skipped, or kept.

Split from `test_claude_instructions.py` by feature — that file is about the byte
budget, this one about the walk that decides whether a pointer's own bytes are
needed at all: how deep a chain may be, what one covered branch says about the
branch beside it, and which plan decides whether a pointer can be dropped.
"""

from unittest.mock import MagicMock, patch

from zrb.llm.prompt.claude import create_project_context_prompt


def _make_ctx():
    ctx = MagicMock()
    ctx.input = MagicMock()
    return ctx


def _identity_next(ctx, prompt):
    return prompt


def test_a_pointer_chain_deeper_than_the_limit_is_not_followed(tmp_path):
    """A thousand nested pointers must not take prompt composition down.

    Following a chain once per hop raised `RecursionError` on a tree of roughly a
    thousand `CLAUDE.md` files. A chain deeper than the limit is treated as
    unresolved: its pointer stays inlined — a line in the prompt, not a crash —
    while the shallow end of the same chain is still followed.
    """
    root = tmp_path / "project"
    root.mkdir()
    (root / "AGENTS.md").write_text("ROOT RULES", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md", encoding="utf-8")
    dirs = [root]
    for _ in range(20):
        parent = dirs[-1] / "d"
        parent.mkdir()
        (parent / "CLAUDE.md").write_text("@../CLAUDE.md", encoding="utf-8")
        dirs.append(parent)
    deepest = dirs[-1]

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=dirs):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS_ENABLED = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 24000
            result = handler(ctx, "base prompt", _identity_next)

    assert "ROOT RULES" in result
    assert f"- `{deepest / 'CLAUDE.md'}`" in result
    assert f"- `{deepest / 'CLAUDE.md'}` — a pointer to" not in result


def test_a_pointer_with_a_deep_branch_is_not_skipped_for_its_shallow_one(tmp_path):
    """One covered branch does not vouch for a branch the walk did not follow.

    `CLAUDE.md` naming `@AGENTS.md` and a chain too deep to follow was skipped for
    the branch that resolved, and the pointer was then the only prompt-visible
    route to the rules at the end of the other one. An unresolved branch keeps
    the whole pointer inlined.
    """
    root = tmp_path / "project"
    root.mkdir()
    (root / "AGENTS.md").write_text("ROOT RULES", encoding="utf-8")
    deep = root / "deep"
    deep.mkdir()
    dirs = [root, deep]
    for index in range(18):
        step = deep / f"d{index}"
        step.mkdir()
        target = f"@../d{index + 1}/CLAUDE.md" if index < 17 else "@../AGENTS.md"
        (step / "CLAUDE.md").write_text(target, encoding="utf-8")
        dirs.append(step)
    (root / "CLAUDE.md").write_text("@AGENTS.md @deep/d0/CLAUDE.md", encoding="utf-8")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=dirs):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS_ENABLED = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 24000
            result = handler(ctx, "base prompt", _identity_next)

    assert "ROOT RULES" in result
    assert f"#### Instructions from: `{root / 'CLAUDE.md'}`" in result
    assert f"- `{root / 'CLAUDE.md'}` — a pointer to" not in result


def test_a_pointer_does_not_promise_a_target_the_walk_dropped(tmp_path):
    """A restored pointer can spend the bytes its target was budgeted.

    The plan drops every pointer, so a pointer the plan kept looks free — it is
    not. The more specific file here is a pointer whose reference resolves
    nowhere, and it spends thirteen bytes the plan had counted on the 1,490-byte
    target, which then falls out of the final walk. The listing must not go on
    saying the pointer names a file the prompt does not carry.
    """
    root = tmp_path / "project"
    app = root / "app"
    sub = app / "sub"
    sub.mkdir(parents=True)
    (root / "AGENTS.md").write_text("R" * 1489 + "\n")  # 1,490 bytes
    (sub / "CLAUDE.md").write_text("@../../AGENTS.md")  # 18 bytes
    (app / "CLAUDE.md").write_text("@missing.md")  # 13 bytes, resolves nowhere

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories", return_value=[root, app, sub]
    ):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS_ENABLED = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 1500
            result = handler(ctx, "base prompt", _identity_next)

    assert f"#### Instructions from: `{root / 'AGENTS.md'}`" not in result
    assert f"— a pointer to `{root / 'AGENTS.md'}`" not in result
    assert f"#### Instructions from: `{sub / 'CLAUDE.md'}`" in result


def test_a_pointer_does_not_starve_the_rules_it_points_at(tmp_path):
    """Thirteen bytes of pointer must not cost the 1,490-byte file behind it.

    The pointer is skipped when the plan that skips every pointer carries its
    target: at a 1,500-byte budget the rules fit once the pointer's own bytes are
    not spent on them. Judged against the first plan instead, the walk inlined
    the pointer, dropped the rules, and with three more bytes inlined the target
    — a worse prompt for a smaller budget.
    """
    root = tmp_path / "project"
    app = root / "app"
    app.mkdir(parents=True)
    (root / "AGENTS.md").write_text("R" * 1489 + "\n")  # 1,490 bytes
    (app / "CLAUDE.md").write_text("@../AGENTS.md")  # 13 bytes

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories", return_value=[root, app]
    ):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS_ENABLED = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 1500
            result = handler(ctx, "base prompt", _identity_next)

    assert "R" * 20 in result
    assert str(app / "CLAUDE.md") in result
    assert "— a pointer to" in result
