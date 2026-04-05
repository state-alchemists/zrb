"""JournalingHookHandler: Reminds LLM to journal at session end.

The LLM already has journal mandate (HOW/WHAT to journal).
This hook provides the WHEN - a reminder at strategic moments.

The hook does NOT:
- Extract learnings (LLM does this)
- Write to journal (LLM uses Write/Edit tools)
- Parse or summarize (LLM's intelligence)

The hook DOES:
- Remind LLM at SESSION_END to consider journaling
- Let LLM decide what's worth remembering
"""

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.types import HookEvent


class JournalingHookHandler:
    """Hook handler that reminds LLM to journal at session end.

    Design principle: Remind, don't replace.
    - Mandate tells LLM HOW/WHAT to journal
    - This hook provides the WHEN (a trigger at the right moment)
    - LLM uses its own intelligence + Write/Edit tools

    Anti-recursion protection:
    - _session_had_significant_activity: Set by POST_TOOL_USE
    - _session_end_fired: Set after reminder sent, prevents repeat firing
    - Reset at SESSION_START for fresh session
    """

    def __init__(self):
        self._session_had_significant_activity: bool = False
        self._session_end_fired: bool = False

    def is_enabled(self) -> bool:
        """Check if journaling is enabled.

        Must check config dynamically because CFG.LLM_INCLUDE_JOURNAL can change
        at runtime (environment variables can be modified between sessions).
        """
        return CFG.LLM_INCLUDE_JOURNAL

    async def handle_event(self, context: HookContext) -> HookResult:
        """Handle hook event - remind LLM to journal at session end.

        This is the main entry point called by HookManager.
        """
        if not self.is_enabled():
            return HookResult()

        # Track if session had meaningful activity
        if context.event == HookEvent.POST_TOOL_USE:
            # Only set flag, don't capture content
            self._session_had_significant_activity = True

        # At SESSION_END, provide reminder if there was activity (once per session)
        if context.event == HookEvent.SESSION_END:
            # Prevent infinite recursion: only fire reminder once per session
            if self._session_end_fired:
                return HookResult()

            if self._session_had_significant_activity:
                # Mark as fired to prevent repeating the reminder
                self._session_end_fired = True
                # Remind LLM to journal - inject system message into conversation
                return HookResult.with_system_message(self._build_reminder())

        return HookResult()

    def _build_reminder(self) -> str:
        """Build reminder message for journaling.

        Simple and direct - the extended session is a side effect,
        so this message is only seen by the LLM during journaling.
        """
        return (
            "Review this session for journal-worthy learnings. "
            "If any, Write/Edit the journal. "
            "Otherwise, acknowledge briefly."
        )

    def reset(self) -> None:
        """Reset session state for new session."""
        self._session_had_significant_activity = False
        self._session_end_fired = False


# Factory function for hook registration
def create_journaling_hook() -> HookCallable:
    """Create journaling hook handler instance.

    Returns the async handler method.
    """
    handler = JournalingHookHandler()
    return handler.handle_event


def create_journaling_hook_factory():
    """Create a factory function for journaling hook registration.

    Returns a factory that checks CFG.LLM_INCLUDE_JOURNAL at execution time.
    This allows the hook to be enabled/disabled without reloading.

    Usage:
        llm_chat.add_hook_factory(create_journaling_hook_factory())
    """
    from zrb.llm.hook.manager import HookManager

    def factory(manager: HookManager):
        # Check config at execution time (not registration time)
        if not CFG.LLM_INCLUDE_JOURNAL:
            return

        journal_hook = create_journaling_hook()
        manager.register(
            journal_hook,
            events=[
                HookEvent.SESSION_START,  # Reset state
                HookEvent.POST_TOOL_USE,  # Track activity
                HookEvent.SESSION_END,  # Send reminder
            ],
        )

    return factory
