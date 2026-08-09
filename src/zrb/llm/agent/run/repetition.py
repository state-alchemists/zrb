"""Detect a model that has stopped generating and started repeating itself.

A degenerate stream is not a slow stream: it never ends on its own, so nothing
downstream of the model ever gets a turn. The request cap
(``LLM_MAX_REQUEST_PER_RUN``) cannot see it because the loop happens *inside*
one response, and the empty-completion guard cannot see it because the response
is not empty. Only the wall clock stops it, and by then the run has spent
everything it was going to spend.

**Why repetition rather than volume.** A cumulative output cap was the obvious
first reach and it does not separate the two populations: the worst degeneration
measured emitted roughly 44k output tokens before its 600s kill, while a healthy
``research`` run in the same grid legitimately emitted 73,440. Any cap that
spares the second lets the first run for the better part of an hour. What the
two do not share is *shape* — the healthy run's output is novel line after line,
the degenerate one cycles a handful of lines forever.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field

#: How few distinct lines, across a full window, mean "cycling" rather than
#: "writing". Not 1: the observed failure alternated a sentence with a stray
#: code fence, so a strict "same line N times" test never fired. A handful of
#: distinct lines repeated for the whole window is the actual signature.
MAX_DISTINCT_LINES = 4


@dataclass
class RepetitionDetector:
    """Flags a response whose last *window* lines cycle a few values forever.

    Fed the text deltas of a single model response. ``window`` of 0 disables it
    — the escape hatch for the false positive this cannot rule out, since
    "generated prose never repeats" is a heuristic about models, not a fact
    about text.
    """

    window: int
    _lines: deque[str] = field(default_factory=deque)
    _partial: str = ""

    def __post_init__(self) -> None:
        self._lines = deque(maxlen=self.window or 1)

    def feed(self, delta: str) -> bool:
        """Absorb one text delta; ``True`` once the response looks degenerate.

        Only completed lines are judged, so the caller may feed deltas of any
        size — the same text split differently reaches the same verdict.
        """
        if self.window <= 0 or not delta:
            return False
        self._partial += delta
        if "\n" not in self._partial:
            # ponytail: a cycle that never emits a newline slips through until
            # it does. Track a rolling character window if one ever shows up.
            return False
        *complete, self._partial = self._partial.split("\n")
        for line in complete:
            stripped = line.strip()
            if stripped:
                self._lines.append(stripped)
        return self.is_degenerate

    @property
    def is_degenerate(self) -> bool:
        """Whether a full window has gone by with almost nothing new in it."""
        if self.window <= 0 or len(self._lines) < self.window:
            return False
        return len(set(self._lines)) <= MAX_DISTINCT_LINES

    def reset(self) -> None:
        """Forget the current response. Called between responses in a run."""
        self._lines.clear()
        self._partial = ""


#: Tools whose contract *is* "call me again with the same arguments". Repetition
#: is how they work, so the consecutive-call counter must not read them as a
#: loop. Everything else re-issuing a byte-identical call learns nothing new.
POLLING_TOOLS = frozenset({"MonitorProcess", "GetDelegationResult"})


@dataclass
class RepeatedCallDetector:
    """Counts a tool call re-issued with byte-identical arguments, back to back.

    The commoner sibling of the text loop above, and the more expensive one: it
    survives every guard because each call is a *legitimate* call. Benchmarking
    found an agent that finished a 44-site migration correctly and then issued
    the same `grep -rl "new_auth("` roughly a hundred times until the wall clock
    stopped it — scored 1.0 on the work and recorded as a timeout.

    **Consecutive** is what makes this safe. A run-fix-run debug cycle re-issues
    the same `pytest` many times and is the loop working as intended, but an
    `Edit` lands between the runs, so the streak resets. A streak means nothing
    happened in between, and a call whose arguments have not changed since the
    last one cannot return anything its predecessor did not.
    """

    limit: int
    _last: str = ""
    _streak: int = 0

    def check(self, name: str, args: object) -> bool:
        """Record a call; ``True`` if it repeats one time too many.

        A verdict is never fatal on its own — the caller turns it into a message
        the model can act on, because the model is the only thing that can
        decide whether to finish or change approach.
        """
        if self.limit <= 0 or name in POLLING_TOOLS:
            return False
        key = f"{name}:{_stable(args)}"
        self._streak = self._streak + 1 if key == self._last else 1
        self._last = key
        return self._streak > self.limit


def _stable(args: object) -> str:
    """A comparable rendering of tool arguments, order-insensitive.

    ``sort_keys`` so a provider that reorders keys between calls does not hide a
    repeat; ``default=str`` because the only thing done with the result is
    comparing it to the previous one.
    """
    try:
        return json.dumps(args, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001 - an uncomparable arg is simply never equal
        return repr(args)
