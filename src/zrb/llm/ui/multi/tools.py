"""A tool call's lifecycle, as this wrapper answers for it.

`AnyUITools` asks a UI to open and close a call, to carry the live shell
output, and to get a decision out of the human. Each child keeps its own
running-tool timer and its own approval prompt, so this module forwards the
first three and resolves the fourth by the priority `MultiUI` has always used.
"""

from typing import Any

from zrb.llm.approval.any_approval_channel import ApprovalContext

from zrb.llm.ui.multi.fanout import MultiUIFanout


class MultiUIToolForwards(MultiUIFanout):
    """Forward the tool-call lifecycle; confirm once, for the whole wrapper."""

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

    async def confirm_tool_execution(self, call: Any):
        """Handle tool execution confirmation.

        Priority:
        1. Use MultiUI's handler if available (has formatters from default UI)
        2. Fall back to winning UI's handler if available
        3. Fall back to approval channel (Telegram buttons)
        """
        if self._tool_call_handler is not None:
            return await self._tool_call_handler.handle(self, call)

        winning_ui = self.last_winning_ui
        winning_handler = (
            winning_ui.tools.tool_call_handler if winning_ui is not None else None
        )
        if winning_handler is not None:
            return await winning_handler.handle(self, call)

        if self._approval_channel is not None:
            context = ApprovalContext(
                tool_name=call.tool_name,
                tool_args=call.args if isinstance(call.args, dict) else {},
                tool_call_id=call.tool_call_id,
            )
            result = await self._approval_channel.request_approval(context)
            return result.to_pydantic_result()

        # Final fallback: the primary child's own handler.
        main_ui = self.main_ui
        if main_ui is not None and main_ui.tools.tool_call_handler is not None:
            return await main_ui.tools.tool_call_handler.handle(self, call)

        raise RuntimeError(
            "MultiUI has no attached UI and no approval channel that can "
            "confirm this tool call — construct it with at least one UI, or "
            "call set_approval_channel(...) before running."
        )
