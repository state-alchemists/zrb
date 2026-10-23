"Git shrinks to a delta against the previous turn; time always renders in full."

import subprocess
from unittest.mock import MagicMock

from zrb.context.any_context import AnyContext
from zrb.llm.prompt.live_context import last_live_context, render_live_context


def _git(repo, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "a.txt").write_text("a")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "alpha-commit")
    return tmp_path


def _ctx() -> AnyContext:
    return MagicMock(spec=AnyContext)


def test_first_turn_renders_the_full_git_state(tmp_path, monkeypatch):
    monkeypatch.chdir(_repo(tmp_path))

    rendered = render_live_context(_ctx())

    assert "- Git:" in rendered
    assert "- Recent commits:" in rendered
    assert "- Worktrees:" in rendered


def test_time_always_renders_and_unchanged_git_is_one_line(tmp_path, monkeypatch):
    monkeypatch.chdir(_repo(tmp_path))
    first = render_live_context(_ctx())

    second = render_live_context(_ctx(), previous_live_context=first)

    assert "- Time:" in second
    assert "- Git: unchanged since the last turn." in second
    assert "- Recent commits:" not in second


def test_only_the_new_commit_is_shown(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    first = render_live_context(_ctx())
    (repo / "b.txt").write_text("b")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "beta-commit")

    second = render_live_context(_ctx(), previous_live_context=first)

    assert "- Recent commits (new since the last turn):" in second
    assert "beta-commit" in second
    assert "alpha-commit" not in second


def test_a_status_change_is_shown(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    first = render_live_context(_ctx())
    (repo / "uncommitted.txt").write_text("x")

    second = render_live_context(_ctx(), previous_live_context=first)

    assert "- Git:" in second
    assert "Dirty" in second


def test_a_branch_change_is_shown(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    first = render_live_context(_ctx())
    _git(repo, "checkout", "-q", "-b", "feature")

    second = render_live_context(_ctx(), previous_live_context=first)

    assert "- Git: feature" in second


def _message(block: str):
    message = MagicMock()
    part = MagicMock()
    part.content = f"question\n\n<live-context>{block}</live-context>"
    message.parts = [part]
    return message


def test_a_partial_delta_does_not_replay_old_commits(tmp_path, monkeypatch):
    """A delta block omits the sections that did not change, so the next turn
    must merge it with the older blocks before diffing. Otherwise every old
    commit reads as new."""
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    first = render_live_context(_ctx())
    (repo / "a.txt").write_text("dirty")
    second = render_live_context(_ctx(), previous_live_context=first)
    assert "- Recent commits" not in second

    baseline = last_live_context([_message(first), _message(second)])
    third = render_live_context(_ctx(), previous_live_context=baseline)

    assert "- Git: unchanged since the last turn." in third
    assert "- Recent commits (new since the last turn):" not in third


def test_last_live_context_reads_a_string_prompt():
    message = MagicMock()
    part = MagicMock()
    part.content = "question\n\n<live-context>- Time: now</live-context>"
    message.parts = [part]

    assert last_live_context([message]) == "- Time: now"


def test_last_live_context_reads_a_multimodal_prompt():
    message = MagicMock()
    part = MagicMock()
    part.content = ["describe this", "<live-context>- Time: now</live-context>"]
    message.parts = [part]

    assert last_live_context([message]) == "- Time: now"


def test_last_live_context_follows_a_rewind():
    """After /rewind the history is truncated, so the newest block is the one
    at the rewound point, not the block the user had before rewinding."""
    old = MagicMock()
    old_part = MagicMock()
    old_part.content = "q1\n\n<live-context>- Time: old</live-context>"
    old.parts = [old_part]
    new = MagicMock()
    new_part = MagicMock()
    new_part.content = "q2\n\n<live-context>- Time: new</live-context>"
    new.parts = [new_part]

    assert last_live_context([old, new]) == "- Time: new"
    assert last_live_context([old]) == "- Time: old"
    assert last_live_context([]) is None
