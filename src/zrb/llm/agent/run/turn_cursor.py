"""`TurnCursor` — the state `_execution_loop` threads across its `while True`.

Sibling to `RetryState`/`RetryOutcome` (`retry_loop.py`), `ExtensionState`
(`session_extension.py`), and `PartialRunAccumulator` (`partial_run.py`) —
this is the same "own the state in a small dataclass next to the loop, not
as loose locals" pattern applied to the one part of the loop that never got
it: `history`, `message`, `results`, `output`, `run_history`, and the
per-turn message accumulator.

Two transitions are protected by name because getting them wrong reintroduces
a real, previously-shipped bug (see `commit_round` and `carry_forward`);
everything else is a plain field, mutated directly by `_execution_loop`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zrb.llm.agent.run.history_utils import TurnPruneFloor


@dataclass
class TurnCursor:
    history: list[Any]
    message: Any = None
    results: Any = None
    output: Any = None
    run_history: list[Any] = field(default_factory=list)
    # This whole logical turn's new messages, accumulated per `commit_round`
    # call — NOT a single slice taken at the end against a fixed baseline.
    # See `commit_round`'s docstring for why that distinction matters.
    accumulated: list[Any] = field(default_factory=list)
    round_baseline: int = field(default=0, repr=False)

    def begin_round(self, sanitized_history: list[Any]) -> None:
        """Start one `agent.run()` round: install the sanitized history and
        record its length as this round's baseline for `commit_round`."""
        self.history = sanitized_history
        self.round_baseline = len(sanitized_history)

    def commit_round(self) -> None:
        """Fold this round's own new messages (since `begin_round`) into the
        turn's accumulator.

        Call before any reassignment of `history`/`run_history` (e.g.
        `carry_forward`) — the slice bounds come from `round_baseline`, set
        fresh by `begin_round` every iteration. Skipping this, or replacing
        it with a single slice taken once at the end of the turn against a
        fixed baseline, silently drops every tool call approved in an
        earlier round of a multi-round turn — exactly the turn a human had
        to approve a `Write` in.
        """
        self.accumulated.extend(self.run_history[self.round_baseline :])

    def carry_forward(self) -> None:
        """After a resolved deferred-tool round: `history` becomes
        `run_history` unconditionally, so the summarizer is never reapplied
        mid-deferral. `process_deferred_requests` already
        populated every resolved call's approval, so there is nothing left
        for a processor to do — reapplying one risks dropping the very turn
        holding the approved call.
        """
        self.history = self.run_history

    @property
    def prune_floor(self) -> TurnPruneFloor:
        """The `drop_oldest_turn` floor implied by the current cursor state
        — see `TurnPruneFloor`."""
        return (
            TurnPruneFloor.KEEP_DEFERRED_TURN
            if self.results is not None
            else TurnPruneFloor.ANY_TURN_MAY_DROP
        )
