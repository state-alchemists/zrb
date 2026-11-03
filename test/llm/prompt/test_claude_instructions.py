"""Instruction inlining: what the prompt carries and what it only lists.

Split from `test_claude.py` by feature: that file covers the documentation
listing, this one the byte budget inside it — which files are inlined, which are
truncated, what a pure `@AGENTS.md` pointer costs, and when a pointer is what
the prompt already has.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.prompt.claude import _read_instruction_bytes, create_project_context_prompt
from zrb.llm.util.prompt import expand_prompt


def _make_ctx():
    ctx = MagicMock()
    ctx.input = MagicMock()
    return ctx


def _identity_next(ctx, prompt):
    return prompt


def test_create_project_context_prompt_inlines_instructions_by_default(tmp_path):
    "The default inlines instruction content instead of only listing the path."
    for name in ("AGENTS.md", "CLAUDE.md"):
        (tmp_path / name).write_text("Some content here")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "### Workspace Instructions" in result
    assert result.count("Some content here") == 2
    assert "— inlined above" in result
    assert "AGENTS.md" in result
    assert "CLAUDE.md" in result


def test_create_project_context_prompt_injection_can_be_turned_off(tmp_path):
    "With injection off, content stays out and the files are listed by path."
    (tmp_path / "AGENTS.md").write_text("Some content here")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS = False
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 24000
            result = handler(ctx, "base prompt", _identity_next)

    assert "Some content here" not in result
    assert "AGENTS.md" in result


def test_create_project_context_prompt_readme_is_never_inlined(tmp_path):
    "README.md is documentation to search, not rules to obey."
    (tmp_path / "AGENTS.md").write_text("Agent content")
    (tmp_path / "README.md").write_text("Readme content")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "Agent content" in result
    assert "Readme content" not in result


def test_instructions_inline_the_most_specific_file_first(tmp_path):
    "A parent-directory AGENTS.md does not preempt the one nearest the work."
    parent = tmp_path / "project"
    child = parent / "service"
    child.mkdir(parents=True)
    (parent / "AGENTS.md").write_text("PARENT RULES")
    (child / "AGENTS.md").write_text("CHILD RULES")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories",
        return_value=[parent, child],
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert result.index("CHILD RULES") < result.index("PARENT RULES")


def test_instructions_budget_truncates_the_nearest_file(tmp_path):
    "An over-budget nearest file is truncated; a broader one stays listed."
    parent = tmp_path / "project"
    child = parent / "service"
    child.mkdir(parents=True)
    (child / "AGENTS.md").write_text("X" * 2000)
    (parent / "AGENTS.md").write_text("PARENT RULES")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories",
        return_value=[parent, child],
    ):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 700
            result = handler(ctx, "base prompt", _identity_next)

    assert "TRUNCATED" in result
    assert "PARENT RULES" not in result
    assert str(parent / "AGENTS.md") in result


def test_no_instructions_are_inlined_when_the_budget_cannot_fit_the_nearest(tmp_path):
    """A budget too small for the nearest file must not admit a broader one.

    Regression: the loop used to `continue` past an over-budget nearest file, so
    a small parent AGENTS.md could still be inlined — handing the model broader
    rules while withholding the rules for the directory being edited.
    """
    parent = tmp_path / "project"
    child = parent / "service"
    child.mkdir(parents=True)
    (child / "AGENTS.md").write_text("X" * 2000)
    (parent / "AGENTS.md").write_text("PARENT RULES")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories",
        return_value=[parent, child],
    ):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 400
            result = handler(ctx, "base prompt", _identity_next)

    assert "Workspace Instructions" not in result
    assert "PARENT RULES" not in result
    assert str(child / "AGENTS.md") in result
    assert str(parent / "AGENTS.md") in result


def test_inlining_stops_at_the_first_file_that_does_not_fit(tmp_path):
    "A grandparent file is not inlined past a parent that was dropped."
    grandparent = tmp_path / "org"
    parent = grandparent / "project"
    child = parent / "service"
    child.mkdir(parents=True)
    (child / "AGENTS.md").write_text("CHILD RULES")
    (parent / "AGENTS.md").write_text("P" * 2000)
    (grandparent / "AGENTS.md").write_text("GRANDPARENT RULES")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories",
        return_value=[grandparent, parent, child],
    ):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 1000
            result = handler(ctx, "base prompt", _identity_next)

    assert "CHILD RULES" in result
    assert "GRANDPARENT RULES" not in result
    assert str(grandparent / "AGENTS.md") in result


def test_include_only_file_does_not_pay_for_its_target_twice(tmp_path):
    """CLAUDE.md holding `@AGENTS.md` must not buy AGENTS.md a second time.

    Regression: the include was inlined verbatim, and `expand_prompt` — run over
    the composed prompt when the agent is built — turned it into an Appendix
    carrying the whole target. The project's rules rode in twice and the byte
    budget accounted for the eleven bytes of the pointer, not the file behind it.
    """
    from zrb.llm.util.prompt import expand_prompt

    (tmp_path / "AGENTS.md").write_text("PROJECT RULES")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert result.count("PROJECT RULES") == 1
    assert "@AGENTS.md" not in result
    assert expand_prompt(result).count("PROJECT RULES") == 1
    # The file is still listed — and says what it is, so nobody opens it twice.
    assert str(tmp_path / "CLAUDE.md") in result
    assert "— a pointer to" in result


def test_a_pointer_in_a_subdirectory_is_skipped_too(tmp_path):
    """A pointer more specific than its target must still be recognised.

    Regression: the pointer was judged against what had been inlined so far, and
    the walk goes most specific first — so `app/CLAUDE.md` naming `@../AGENTS.md`
    was inlined (the parent had not been reached yet) and the parent's rules
    arrived twice. That is the layout an agent runs in whenever it starts from a
    subdirectory.
    """
    root = tmp_path / "project"
    app = root / "app"
    app.mkdir(parents=True)
    (root / "AGENTS.md").write_text("PARENT RULES")
    (app / "CLAUDE.md").write_text("@../AGENTS.md")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories", return_value=[root, app]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert result.count("PARENT RULES") == 1
    assert "@../AGENTS.md" not in result


def test_a_pointer_whose_target_was_dropped_is_still_inlined(tmp_path):
    """Skipping a pointer must not cut the last route to its target's rules.

    Regression: the redundancy check ran against every instruction candidate
    rather than against what the prompt actually carries, so a pointer at a
    parent file the byte budget then dropped was skipped anyway — and the
    parent's rules reached the prompt by no route at all.
    """
    parent = tmp_path / "project"
    child = parent / "service"
    child.mkdir(parents=True)
    (child / "AGENTS.md").write_text("CHILD RULES")
    (child / "CLAUDE.md").write_text("@../AGENTS.md")
    (parent / "AGENTS.md").write_text("PARENT RULES " + "P" * 2000)

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories",
        return_value=[parent, child],
    ):
        with patch("zrb.llm.prompt.claude.CFG") as cfg:
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 200
            result = handler(ctx, "base prompt", _identity_next)

    assert "CHILD RULES" in result
    assert "../AGENTS.md" in result
    assert "@../AGENTS.md" not in result
    assert "PARENT RULES" not in result


def test_include_carrying_prose_of_its_own_is_still_inlined(tmp_path):
    "Only a pure include is dropped; a file that also writes rules keeps them."
    (tmp_path / "AGENTS.md").write_text("PROJECT RULES")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n\nAlso: prefer ruff.")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "Also: prefer ruff." in result


def test_include_of_a_file_outside_the_instruction_set_is_kept(tmp_path):
    "An include nothing else would load is kept as a path the model can open."
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "rules.md").write_text("HOUSE RULES")
    (tmp_path / "CLAUDE.md").write_text("@docs/rules.md")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "docs/rules.md" in result
    assert "@docs/rules.md" not in result


def test_a_reference_inside_inlined_rules_is_never_expanded(tmp_path):
    """`@path` in a rule file must not fetch that file into the prompt.

    `expand_prompt` runs over the composed system prompt when the agent is
    built, resolving every `@path` it finds — no byte budget, no project
    boundary. A rule file naming an absolute path would have that file read and
    sent to the provider with nothing in the user's view to show it happened.
    """
    secret = tmp_path / "credentials"
    secret.write_text("AWS_SECRET_ACCESS_KEY=leaked", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(f"Deploy details: @{secret}", encoding="utf-8")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    expanded = expand_prompt(result)
    assert "leaked" not in expanded
    # The path survives as text, so a deliberate Read still finds it.
    assert str(secret.resolve()) in expanded


def test_a_chain_of_pointers_names_the_file_the_prompt_holds(tmp_path):
    """A pointer to a pointer is described by what the prompt actually carries.

    `CLAUDE.md -> @GEMINI.md -> @AGENTS.md` is two hops, and a listing that named
    the middle file would say "inlined above" about something that is not.
    """
    agents = tmp_path / "AGENTS.md"
    agents.write_text("ROOT RULES")
    (tmp_path / "GEMINI.md").write_text("@AGENTS.md")
    (tmp_path / "CLAUDE.md").write_text("@GEMINI.md")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert result.count("ROOT RULES") == 1
    assert f"— a pointer to `{agents.resolve()}`" in result


def test_pointers_that_circle_each_other_name_no_file(tmp_path):
    """A cycle has no terminal file, so the listing must not pretend it has one."""
    (tmp_path / "CLAUDE.md").write_text("@GEMINI.md")
    (tmp_path / "GEMINI.md").write_text("@CLAUDE.md")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "— a pointer to" not in result
    assert "Workspace Instructions" not in result


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
            cfg.LLM_INJECT_PROJECT_INSTRUCTIONS = True
            cfg.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES = 1500
            result = handler(ctx, "base prompt", _identity_next)

    assert "R" * 20 in result
    assert str(app / "CLAUDE.md") in result
    assert "— a pointer to" in result


def test_a_path_with_an_at_sign_is_not_a_second_reference(tmp_path, monkeypatch):
    """An `@` in a directory name is part of the path, not a fetch.

    `expand_prompt` runs over the composed system prompt and resolves every
    `@path` it finds with no budget and no project boundary. A project under
    `@scope` used to have its own listing re-read as a reference to `<cwd>/scope`
    — a different file, appended to the prompt with nothing in the user's view
    to show it happened.
    """
    project = tmp_path / "@scope"
    project.mkdir()
    (project / "AGENTS.md").write_text("REAL RULES", encoding="utf-8")
    (project / "scope").mkdir()
    (project / "scope" / "AGENTS.md").write_text("A FILE NOBODY NAMED", encoding="utf-8")
    monkeypatch.chdir(project)

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude.get_search_directories", return_value=[project]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    expanded = expand_prompt(result)
    assert "REAL RULES" in expanded
    assert "A FILE NOBODY NAMED" not in expanded
    assert expanded.count("REAL RULES") == 1


def test_a_hardlinked_instruction_file_is_listed_but_never_inlined(tmp_path):
    """A hardlink is not a symlink, and reading it leaks the file it shares.

    `AGENTS.md` hardlinked to a key has that key's bytes, and the path itself
    says nothing about where they came from. The file is still listed, so
    opening it stays a deliberate act.
    """
    project = tmp_path / "project"
    project.mkdir()
    secret = tmp_path / "id_rsa"
    secret.write_text("PRIVATE KEY MATERIAL", encoding="utf-8")
    try:
        os.link(secret, project / "AGENTS.md")
    except (OSError, NotImplementedError):
        pytest.skip("this platform does not let an unprivileged test hardlink")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[project]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "PRIVATE KEY MATERIAL" not in result
    assert "### Workspace Instructions" not in result
    assert f"- `{project / 'AGENTS.md'}`" in result


def test_a_symlinked_instruction_file_is_listed_but_never_inlined(tmp_path):
    """`AGENTS.md -> ~/.ssh/id_rsa` must not put the target into the prompt.

    The link can name any readable file on the machine, and inlined content is
    sent to the model provider before the user has read it. The file is still
    listed, so opening it stays possible as a deliberate act.
    """
    project = tmp_path / "project"
    project.mkdir()
    secret = tmp_path / "id_rsa"
    secret.write_text("PRIVATE KEY MATERIAL")
    try:
        (project / "AGENTS.md").symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("this platform does not let an unprivileged test create a symlink")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[project]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "PRIVATE KEY MATERIAL" not in result
    assert "### Workspace Instructions" not in result
    assert f"- `{project / 'AGENTS.md'}`" in result


def test_reading_an_instruction_file_stops_at_the_budget(tmp_path):
    """The read is bounded by the budget, not the file: one byte over, never more.

    A file bigger than the budget can contribute nothing past it, so loading the
    whole thing first would let a huge (or hostile) instruction file exhaust
    memory before the budget was ever consulted. The extra byte is all the walk
    needs to tell "fits" from "is longer".
    """
    huge = tmp_path / "AGENTS.md"
    huge.write_text("x" * 2_000_000, encoding="utf-8")

    assert len(_read_instruction_bytes(huge, 1_000)) == 1_001

    # Bytes, not text: text mode turns "\n" into "\r\n" on Windows.
    small = tmp_path / "CLAUDE.md"
    small.write_bytes(b"RULES\n")
    assert _read_instruction_bytes(small, 1_000) == b"RULES\n"
