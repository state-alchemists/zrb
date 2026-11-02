"""The deterministic pruner: a budget, a marker, and a pointer to the text."""

import os
import stat

import pytest

from zrb.llm.summarizer.tool_result_pruner import (
    PRUNED_PREFIX,
    is_pruned_tool_result,
    prune_tool_result_content,
    spill_tool_result,
    tool_result_spill_dir,
)


class CharLimiter:
    """One token per character, so the budgets are exact."""

    def count_tokens(self, content) -> int:
        return len(str(content))

    def truncate_text(self, text: str, limit: int) -> str:
        return text[:limit]


def test_the_pruned_text_keeps_a_measured_head_and_tail():
    limiter = CharLimiter()
    content = "head " + "m" * 1000 + " tail"

    pruned = prune_tool_result_content(content, limiter, 200, spill_path=None)

    assert pruned.startswith(PRUNED_PREFIX)
    assert "head " in pruned
    assert " tail" in pruned
    assert "m" * 1000 not in pruned
    assert "[... " in pruned and "tokens pruned ...]" in pruned


def test_the_marker_names_the_spill_file_when_there_is_one():
    limiter = CharLimiter()
    content = "A" * 1000

    pruned = prune_tool_result_content(
        content, limiter, 100, spill_path="/tmp/full-output.txt"
    )

    assert "Full output: `/tmp/full-output.txt`" in pruned


def test_the_marker_says_so_when_the_text_could_not_be_saved():
    limiter = CharLimiter()

    pruned = prune_tool_result_content("A" * 1000, limiter, 100, spill_path=None)

    assert "could not be saved" in pruned


def test_the_spill_file_lives_beside_the_conversations_archive(tmp_path):
    directory = tool_result_spill_dir("my-session", str(tmp_path))

    assert directory == os.path.join(
        str(tmp_path), "verbatim", "my-session.tool-results"
    )


def test_an_unnamed_conversation_still_gets_one_directory(tmp_path):
    directory = tool_result_spill_dir(None, str(tmp_path))

    assert directory.endswith(os.path.join("verbatim", "_unassigned.tool-results"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits")
def test_the_verbatim_text_survives_and_is_owner_only(tmp_path):
    content = "line one\nline two\n" * 1000
    path = spill_tool_result(
        content, call_id="call-1", session_name="s", history_dir=str(tmp_path)
    )

    assert path is not None
    with open(path, encoding="utf-8") as spill_file:
        assert spill_file.read() == content
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_a_write_failure_returns_no_pointer(tmp_path, monkeypatch):
    from zrb.llm.summarizer import tool_result_pruner

    monkeypatch.setattr(
        tool_result_pruner,
        "write_text_owner_only",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    assert (
        spill_tool_result(
            "text", call_id="c", session_name="s", history_dir=str(tmp_path)
        )
        is None
    )


@pytest.mark.parametrize(
    "content, expected",
    [
        (f"{PRUNED_PREFIX} 1 of 2 tokens kept", True),
        ("SUMMARY OF TOOL RESULT: old", False),
        ("ordinary output", False),
    ],
)
def test_a_replayed_result_is_recognised_by_its_marker(content, expected):
    assert is_pruned_tool_result(content) is expected
