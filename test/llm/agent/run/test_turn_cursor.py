"""Tests for the two history-transition methods on ``TurnCursor``."""

from zrb.llm.agent.run.history_utils import TurnPruneFloor
from zrb.llm.agent.run.turn_cursor import TurnCursor
from zrb.llm.shared.usage_log import ContextComposition


def test_begin_round_sets_history_and_baseline():
    cursor = TurnCursor(history=["a", "b"])
    cursor.begin_round(["a", "b", "c"])
    assert cursor.history == ["a", "b", "c"]
    assert cursor.round_baseline == 3


def test_commit_round_appends_only_the_new_slice_since_begin_round():
    cursor = TurnCursor(history=[])
    cursor.begin_round(["h1", "h2"])
    cursor.run_history = ["h1", "h2", "new1", "new2"]
    cursor.commit_round()
    assert cursor.accumulated == ["new1", "new2"]


def test_commit_round_accumulates_across_multiple_rounds():
    """The bug class this protects against: a single end-of-turn slice
    against one fixed baseline would drop `new1` once `round_baseline`
    moves for the second round. Accumulating per round must not lose it."""
    cursor = TurnCursor(history=[])
    cursor.begin_round(["h1"])
    cursor.run_history = ["h1", "new1"]
    cursor.commit_round()

    cursor.begin_round(["h1", "new1"])
    cursor.run_history = ["h1", "new1", "new2"]
    cursor.commit_round()

    assert cursor.accumulated == ["new1", "new2"]


def test_carry_forward_sets_history_from_run_history():
    cursor = TurnCursor(history=["stale"], run_history=["fresh1", "fresh2"])
    cursor.carry_forward()
    assert cursor.history == ["fresh1", "fresh2"]


def test_prune_floor_keeps_deferred_turn_when_results_pending():
    cursor = TurnCursor(history=[], results={"some": "result"})
    assert cursor.prune_floor == TurnPruneFloor.KEEP_DEFERRED_TURN


def test_prune_floor_allows_any_turn_to_drop_when_no_results_pending():
    cursor = TurnCursor(history=[], results=None)
    assert cursor.prune_floor == TurnPruneFloor.ANY_TURN_MAY_DROP


def test_the_composition_is_taken_once_so_a_later_round_cannot_repeat_it():
    """Only the first round sends the prepared request, so only it describes it.

    A later round has grown the history by the first round's own answer, and a
    composition copied onto it would report a request that was never sent.
    """
    cursor = TurnCursor(history=[], composition=ContextComposition(1, 2, 3))

    assert cursor.take_composition() == ContextComposition(1, 2, 3)
    assert cursor.take_composition() is None


def test_a_turn_with_no_prepared_request_answers_nothing():
    assert TurnCursor(history=[]).take_composition() is None
