"""Every path from the multi-UI wrapper to the interfaces it wraps.

A `MultiUI` owns no surface of its own: writing, badges, block markers, usage
meters, the shared LLM task and the thinking flag each end in a loop over
`self._uis`. This module is that loop — the two helpers, and every member the
aggregate forwards to its children.

The rule is best-effort throughout: a dead channel is not a dead run, so a
child that raises is logged and skipped rather than allowed to end the turn.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, TextIO

from zrb.config.config import CFG
from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.multi.state import MultiUIState

if TYPE_CHECKING:
    from zrb.llm.agent.types import RequestUsage, RunUsage


class MultiUIFanout(MultiUIState):
    """Reach every child, and let a failing one cost only itself."""

    def append_to_output(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Broadcast output to ALL child UIs."""
        for ui in self._uis:
            try:
                ui.append_to_output(
                    *values, sep=sep, end=end, file=file, flush=flush, kind=kind
                )
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI append_to_output failed: {e}")

    def set_status_badge(self, key: str, text: str | None) -> None:
        self._fanout(
            "set_status_badge", lambda ui: ui.display.set_status_badge(key, text)
        )

    def _fanout(self, name: str, call: Callable[[AnyUI], object]) -> None:
        """Run `call` on every child, best-effort: a dead channel is not a dead
        run. `name` labels the debug line when a child fails."""
        for ui in self._uis:
            try:
                call(ui)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI {name} failed: {e}")

    def _fanout_if_offered(self, method_name: str, /, *args) -> None:
        """Call `method_name` on each child that offers it, best-effort.

        Only for the hooks `AnyUI` leaves undeclared because a child without
        them behaves differently, not merely less (`update_tool_prepare`,
        `update_shell_output`, `finish_shell_output`).
        """
        for ui in self._uis:
            fn = getattr(ui, method_name, None)
            if not callable(fn):
                continue
            try:
                fn(*args)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI {method_name} failed: {e}")

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Forward one run's usage totals to every child UI."""
        self._fanout(
            "accumulate_usage",
            lambda ui: ui.session.accumulate_usage(usage, context_usage),
        )

    def reset_context_usage(self) -> None:
        """Forward a context-size reset to every child UI."""
        self._fanout("reset_context_usage", lambda ui: ui.session.reset_context_usage())

    def append_markdown(self, markdown_text: str) -> None:
        """Render `markdown_text` on every child.

        Children with their own `append_markdown` get the source; others get
        pre-rendered output.
        """
        self._fanout(
            "append_markdown", lambda ui: ui.display.append_markdown(markdown_text)
        )

    def append_answer(self, markdown_text: str) -> None:
        """Append the turn's answer on every child, at the column it keeps.

        A child with its own `append_answer` gets it there; one with only
        `append_markdown` gets the answer through that; a minimal UI with only
        `append_to_output` gets it pre-rendered, by `AnyUI`'s defaults: the
        layout may differ, the text never disappears.
        """
        self._fanout(
            "append_answer", lambda ui: ui.display.append_answer(markdown_text)
        )

    def record_tool_call_block(self, collapsed: str, full: str) -> None:
        """Give every child its tool-call/result line.

        A child that fails to record the block gets a plain `append_to_output`
        instead: the caller sends the line through only one of the two, so
        every child must be reached here.
        """
        for ui in self._uis:
            try:
                ui.display.record_tool_call_block(collapsed, full)
                continue
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI record_tool_call_block failed: {e}")
            try:
                ui.append_to_output(collapsed, end="", kind="tool_call")
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI append_to_output failed: {e}")

    def mark_thinking_block_start(self) -> None:
        """Mark a live thinking block's start on toggle-capable children.

        No fallback needed: the text itself reaches every child through
        `append_to_output`.
        """
        self._fanout(
            "mark_thinking_block_start",
            lambda ui: ui.display.mark_thinking_block_start(),
        )

    def collapse_thinking_block(self, collapsed: str, full: str) -> None:
        """Collapse the block opened by `mark_thinking_block_start`."""
        self._fanout(
            "collapse_thinking_block",
            lambda ui: ui.display.collapse_thinking_block(collapsed, full),
        )

    def mark_text_block_start(self) -> None:
        """Mark the reply block's start on toggle-capable children."""
        self._fanout(
            "mark_text_block_start", lambda ui: ui.display.mark_text_block_start()
        )

    def collapse_text_block(self, collapsed: str, full: str) -> None:
        """Collapse the block opened by `mark_text_block_start`."""
        self._fanout(
            "collapse_text_block",
            lambda ui: ui.display.collapse_text_block(collapsed, full),
        )

    def settle_text_block(self, source: str) -> None:
        """Show an intermediate text block's prose in full on children that can.

        No fallback: a child without the hook keeps the streamed copy it
        already printed, which is the whole text anyway.
        """
        self._fanout(
            "settle_text_block", lambda ui: ui.display.settle_text_block(source)
        )

    def set_stream_indentation(self, indent: str) -> None:
        """Tell children that render a settled block the column to keep.

        A child without the hook keeps its own layout — the same no-fallback
        rule as the hooks above: it is a channel that never asked for the
        column in the first place.
        """
        self._fanout(
            "set_stream_indentation",
            lambda ui: ui.display.set_stream_indentation(indent),
        )

    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """Forward a tool call's start to children tracking the running-tool timer."""
        self._fanout(
            "start_tool_call",
            lambda ui: ui.tools.start_tool_call(tool_name, tool_call_id),
        )

    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """Forward a tool call's end to children tracking the running-tool timer."""
        self._fanout("end_tool_call", lambda ui: ui.tools.end_tool_call(tool_call_id))

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Forward a "Prepare tool parameters" update to children that support it."""
        self._fanout_if_offered("update_tool_prepare", key, text)

    def update_shell_output(self, key: str, text: str) -> None:
        """Forward a live shell-output update to children that support it."""
        self._fanout_if_offered("update_shell_output", key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> None:
        """Collapse `key`'s live shell-output line on children that support it."""
        self._fanout_if_offered("finish_shell_output", key, collapsed, full)

    def replay_history(self, messages: list) -> None:
        """Replay loaded history on every child UI that supports it."""
        self._fanout("replay_history", lambda ui: ui.display.replay_history(messages))

    async def update_system_info(self) -> None:
        """Refresh the status line on every child.

        Best-effort like the rest of this module: a channel that cannot refresh
        keeps the line it has, and the turn is not the place it dies.
        """
        for ui in self._uis:
            try:
                await ui.session.update_system_info()
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI system info update failed: {e}")

    def set_thinking(self, value: bool, repaint: bool = True) -> None:
        """Mirror the thinking flag to every child UI, then repaint.

        Children's status bars read their own `is_thinking`. `repaint=False`
        lets callers refresh system info first.
        """
        self._is_thinking = value
        for ui in self._uis:
            ui.session.is_thinking = value
        if repaint:
            self.invalidate_ui()

    def invalidate_ui(self) -> None:
        """Ask every child UI to repaint."""
        for ui in self._uis:
            try:
                ui.display.invalidate_ui()
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI invalidate_ui failed: {e}")

    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """Release every child's pending confirmation."""
        for ui in self._uis:
            ui.tools.cancel_pending_confirmations(flush)

    def stream_to_parent(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        for ui in self._uis:
            try:
                ui.display.stream_to_parent(
                    *values, sep=sep, end=end, file=file, flush=flush, kind=kind
                )
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI stream_to_parent failed: {e}")
