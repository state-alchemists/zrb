"""Which turns the compliance judge runs on.

`journal_due` is precomputed in the runner because `MatcherConfig` has no OR
primitive; these cases pin the rule it encodes — the judge may want a durable
note, and a day line is not one.
"""

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.agent.run.runner import is_journal_due_for_turn


def _logged_turn(completed: bool) -> list:
    turn: list = [
        ModelResponse(
            parts=[ToolCallPart(tool_name="LogActivity", args={}, tool_call_id="1")]
        )
    ]
    if completed:
        turn.append(
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="LogActivity",
                        content="Logged to activity-log/2026/2026-11/2026-11-03.md",
                        tool_call_id="1",
                    )
                ]
            )
        )
    return turn


def test_a_file_changing_turn_asks_the_judge_even_when_it_logged_a_line():
    """A line records what happened; the judge may still want a note about why."""
    turn = _logged_turn(completed=True)
    assert is_journal_due_for_turn(turn, wrote_files=True, periodic_check=False) is True


def test_a_periodic_check_is_answered_by_a_completed_line():
    turn = _logged_turn(completed=True)
    assert (
        is_journal_due_for_turn(turn, wrote_files=False, periodic_check=True) is False
    )


def test_a_refused_line_leaves_the_periodic_check_due():
    turn = _logged_turn(completed=False)
    assert is_journal_due_for_turn(turn, wrote_files=False, periodic_check=True) is True


def test_a_quiet_turn_is_not_due():
    turn = [ModelResponse(parts=[TextPart(content="done")])]
    assert (
        is_journal_due_for_turn(turn, wrote_files=False, periodic_check=False) is False
    )


def test_a_stated_preference_is_due_whatever_else_happened():
    turn = _logged_turn(completed=True) + [
        ModelRequest(parts=[UserPromptPart(content="from now on use tabs")])
    ]
    assert (
        is_journal_due_for_turn(turn, wrote_files=False, periodic_check=False) is True
    )
