"""Per-turn live-context providers: an ordered, name-keyed list owned by one `PromptManager`."""

from collections.abc import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext

# Returns a string, or None/"" to emit nothing. Lives here so
# `prompt/manager.py` can import it without a cycle.
SimplePrompt = Callable[[AnyContext], "str | None"]


class LiveContextProviders:
    """Named providers called every turn; non-empty output goes into ``<live-context>``."""

    def __init__(self) -> None:
        self._providers: "list[tuple[str, SimplePrompt]]" = []

    def add_provider(self, name: str, provider: "SimplePrompt") -> None:
        """Register *provider* under *name*, replacing any previous one."""
        for i, (existing, _) in enumerate(self._providers):
            if existing == name:
                self._providers[i] = (name, provider)
                return
        self._providers.append((name, provider))

    def remove_provider(self, name: str) -> None:
        """Drop the provider registered under *name*. No-op if absent."""
        self._providers = [(n, p) for n, p in self._providers if n != name]

    def set_providers(self, providers: "list[tuple[str, SimplePrompt]]") -> None:
        """Replace the whole provider list wholesale."""
        self._providers = list(providers)

    def get_providers(self) -> "list[tuple[str, SimplePrompt]]":
        """The `(name, provider)` pairs, in registration order."""
        return list(self._providers)

    def render(self, ctx: AnyContext) -> "list[str]":
        """Every provider's non-empty output, in order; a provider that raises is skipped."""
        parts: list[str] = []
        for name, provider in self._providers:
            try:
                extra = provider(ctx)
            except Exception as e:
                CFG.LOGGER.debug(f"Live-context provider '{name}' failed: {e}")
                continue
            if extra:
                parts.append(extra)
        return parts
