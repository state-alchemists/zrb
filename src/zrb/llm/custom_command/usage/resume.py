"""The `/usage` resume reading: what picking this conversation up costs now.

`/usage` reports what has already been spent. The one number about the *next*
turn is not a spend yet: a history the provider's prompt cache no longer holds
is re-sent whole, and a new session instead pays only its own system prompt.
Measured on 2026-11-12 (board 0003): three turns resuming after 37, 21 and 127
idle minutes paid 351,517 fresh input tokens to produce 5,484 output — a fifth
of that day's fresh input — while a cold session pays 18–24k before the first
word.

Both inputs are already in hand: the conversation's saved history and the
timestamp on its newest message. Reading them costs no model call, and the
usage log is not consulted — the log knows past turns, and the question is
about the next one.

The line is deliberately quiet. It speaks only when the history is large
enough for the difference to matter *and* old enough for the cache to have
lapsed; anything else is a pause, not a gap. The estimate is an upper bound:
it charges the whole history, so a provider still holding part of the prefix
cached makes resuming cheaper than the line says, never dearer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.limiter import get_run_llm_limiter

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI
    from zrb.llm.ui.any_ui_session import AnyUISession

FRESH_SESSION_TOKENS = 20_000
"""What a new session costs before the user has said anything.

Its system prompt and live-context block, measured at 18–24k on the
2026-11-12 log (board 0003). A round midpoint: the line compares two costs, it
does not audit the prompt.
"""


@dataclass(frozen=True)
class ResumeReading:
    """How long the history has sat, and what it holds.

    `history_tokens` is also the resume estimate — the whole history is what
    the next request re-sends — so it is not stored twice.
    """

    idle_seconds: float
    history_tokens: int


def read_resume(ui: "AnyUI | None") -> ResumeReading | None:
    """The reading behind `/usage`'s resume line, or None when none is due.

    None means "say nothing", and covers every reason to: no UI and so no
    session (a headless run names no conversation), a turn still running (a
    live turn is not a resume), no saved history, a history under
    `LLM_UI_USAGE_RESUME_HISTORY_TOKENS`, and a previous turn younger than
    `LLM_UI_USAGE_RESUME_GAP_SECONDS`. Either knob at 0 or below turns the line
    off.

    The gap is judged before the history is counted: counting is the expensive
    half, and most calls arrive nowhere near stale.
    """
    gap_seconds = CFG.LLM_UI_USAGE_RESUME_GAP_SECONDS
    minimum_tokens = CFG.LLM_UI_USAGE_RESUME_HISTORY_TOKENS
    if ui is None or gap_seconds <= 0 or minimum_tokens <= 0:
        return None
    session = ui.session
    if session.is_turn_running:
        return None
    messages = _saved_history(session)
    ended_at = _last_activity_at(messages)
    if ended_at is None:
        return None
    idle_seconds = (datetime.now(timezone.utc) - ended_at).total_seconds()
    if idle_seconds < gap_seconds:
        return None
    history_tokens = get_run_llm_limiter().count_content_tokens(messages)
    if history_tokens < minimum_tokens:
        return None
    return ResumeReading(idle_seconds=idle_seconds, history_tokens=history_tokens)


def _saved_history(session: "AnyUISession") -> list:
    """This session's saved messages, or an empty list when it has none.

    The conversation's own name, not the usage log's stable key: the history
    file is named for the display name, so a renamed conversation reads under
    the name it now holds.
    """
    name = session.conversation_session_name
    history_manager = session.history_manager
    if not name or history_manager is None:
        return []
    return history_manager.load(name)


def _last_activity_at(messages: list) -> datetime | None:
    """When the newest timestamped message was recorded.

    Scanned from the end because the last message is not always stamped: a run
    that failed saves the error as a further `ModelRequest`, which carries no
    timestamp of its own, so the turn really ended at the response before it.
    """
    for message in reversed(messages):
        when = _to_datetime(getattr(message, "timestamp", None))
        if when is not None:
            return when
    return None


def _to_datetime(stamp: object) -> datetime | None:
    """A message timestamp as an aware datetime, or None when it has none.

    A stamp without a zone is read as UTC: pydantic-ai writes aware times, and
    the naive ones this could find come from files a JSON round-trip left with
    their `Z` lost.
    """
    if isinstance(stamp, datetime):
        when = stamp
    elif isinstance(stamp, str):
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)
