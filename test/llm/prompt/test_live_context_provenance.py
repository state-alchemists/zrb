"""Input provenance and linked-worktree lines in the live context."""

from unittest.mock import MagicMock, patch

from zrb.context.any_context import AnyContext
from zrb.llm.input_source import InputProvenance
from zrb.llm.prompt.live_context import render_live_context
from zrb.llm.tool.ambient_state import input_provenance


def test_live_context_includes_input_provenance():
    ctx = MagicMock(spec=AnyContext)
    token = input_provenance.set(InputProvenance("Telegram"))
    try:
        rendered = render_live_context(ctx)
    finally:
        input_provenance.reset(token)

    assert "- Input: user via Telegram" in rendered


def test_live_context_warns_for_transcribed_input():
    ctx = MagicMock(spec=AnyContext)
    token = input_provenance.set(
        InputProvenance("microphone", modality="dictation", transcription=True)
    )
    try:
        rendered = render_live_context(ctx)
    finally:
        input_provenance.reset(token)

    assert "STT transcript may be inaccurate" in rendered


def test_live_context_includes_active_worktrees(tmp_path):
    current = tmp_path / "current"
    other = tmp_path / "other"
    current.mkdir()
    other.mkdir()
    porcelain = (
        f"worktree {current}\nHEAD abc\nbranch refs/heads/main\n\n"
        f"worktree {other}\nHEAD def\nbranch refs/heads/feature\n\n"
        f"worktree {tmp_path / 'gone'}\nHEAD ghi\n"
        "prunable stale\n\n"
    )
    ctx = MagicMock(spec=AnyContext)
    with patch("zrb.llm.prompt.live_context.os.getcwd", return_value=str(current)):
        with patch("zrb.llm.util.git.is_inside_git_dir", return_value=True):
            with patch("subprocess.run") as mock_run:

                def run_git(args, **kwargs):
                    result = MagicMock(returncode=0, stdout="")
                    if args[:4] == ["git", "worktree", "list", "--porcelain"]:
                        result.stdout = porcelain
                    return result

                mock_run.side_effect = run_git
                rendered = render_live_context(ctx)

    assert "- Worktrees:" in rendered
    assert "main @" in rendered and ", current" in rendered
    assert "feature @" in rendered
    assert "gone" not in rendered
