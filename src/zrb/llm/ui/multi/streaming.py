"""One turn, streamed to every child.

The wrapper holds the turn's handle — its children run none of their own, so
`is_turn_running` and the cancel answer here — and runs the turn through
`run_turn`, the same call every UI makes. That one call is what broadcasts the
output, the thinking flag, the plan-mode badge and the system-info refresh to
the children, so a chat with a terminal and a Telegram window shows one turn,
not two.
"""

import asyncio
from typing import TYPE_CHECKING, Any, cast

from zrb.llm.ui.multi.tools import MultiUIToolForwards
from zrb.llm.ui.turn_execution import build_turn_session, run_turn

if TYPE_CHECKING:
    from zrb.llm.ui.multi.multi_ui import MultiUI


def _whole_ui(part: "MultiUIStreaming") -> "MultiUI":
    """This part, as the `MultiUI` it always sits inside.

    A turned part is inherited into the composite and never constructed alone,
    so the cast is a statement of that rule rather than a claim about a value;
    the type system sees the part, while a turn takes the whole.
    """
    return cast("MultiUI", part)


class MultiUIStreaming(MultiUIToolForwards):
    """Run one turn, and show it on every child."""

    def create_session_for_llm_task(
        self,
        user_message: str,
        attachments: list[Any],
    ) -> Any:
        """Create the session a turn runs in; `run_turn` builds its own through
        the same function, taking the name, approval mode and model from the
        primary child."""
        if self.main_ui is None:
            raise RuntimeError(
                "MultiUI has no attached UI to take the session name, approval "
                "mode and model from — construct it with at least one UI."
            )
        return build_turn_session(_whole_ui(self), user_message, attachments)

    async def stream_ai_response(
        self,
        llm_task: Any,
        user_message: str,
        attachments: list[Any] | None = None,
    ):
        """Stream the turn to every child, held as a task so Esc can stop it."""
        task = asyncio.create_task(
            run_turn(_whole_ui(self), llm_task, user_message, attachments)
        )
        self._running_llm_task = task
        try:
            await task
        finally:
            self._running_llm_task = None
