"""JournalingHookHandler: Reminds LLM to journal at the end of every response.

The LLM already has journal mandate (HOW/WHAT to journal).
This hook provides the WHEN - a reminder after every final response,
regardless of whether tool calls were made. Insights worth noting can
arise from pure Q&A conversations just as much as from tool-heavy sessions.

The hook does NOT:
- Extract learnings (LLM does this)
- Write to journal (LLM uses Write/Edit tools)
- Parse or summarize (LLM's intelligence)

The hook DOES:
- Remind LLM at SESSION_END to consider journaling
- Let LLM decide what's worth remembering (it will skip trivial exchanges)
"""

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.types import HookEvent
from zrb.llm.prompt.prompt import get_journal_reminder_prompt


class JournalingHookHandler:
    """Hook handler that reminds LLM to journal at session end.

    Design principle: Remind, don't replace.
    - Mandate tells LLM HOW/WHAT to journal
    - This hook provides the WHEN (a trigger at the right moment)
    - LLM uses its own intelligence + Write/Edit tools

    Anti-recursion protection:
    - _session_end_fired: Set after reminder sent, prevents repeat firing within a turn
    - Reset at SESSION_START so the hook fires again on every new turn
    """

    def __init__(self):
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

        # Reset state at the start of each turn so the hook fires every turn
        if context.event == HookEvent.SESSION_START:
            self.reset()

        # At SESSION_END, always remind — LLM decides whether anything is worth noting
        if context.event == HookEvent.SESSION_END:
            # Prevent infinite recursion: only fire reminder once per turn
            if self._session_end_fired:
                return HookResult()
            self._session_end_fired = True
            return HookResult.with_system_message(self._build_reminder())

        return HookResult()

    def _build_reminder(self) -> str:
        """Build reminder message for journaling.

        Loads from the configurable journal_reminder prompt template,
        which includes the core-journaling skill content (graph structure,
        directory rules, index content).
        """
        return get_journal_reminder_prompt()

    def reset(self) -> None:
        """Reset session state for new turn."""
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
                HookEvent.SESSION_START,  # Reset state each turn
                HookEvent.SESSION_END,  # Send reminder after every response
            ],
        )

    return factory
