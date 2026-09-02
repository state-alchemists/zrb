"""Per-turn live-context providers, composed by `PromptManager`.

Not a registry in the ADR-0090 sense: no `CFG` twin, no discovery layer, no
layering over anything — just an ordered, name-keyed list of callables owned
by one `PromptManager` instance. Promoting it to a public registry (a
`CFG.LLM_LIVE_CONTEXT` twin, a module singleton) would serve a single call
site (`PromptManager.add_live_context`) for no benefit. What it does need is
the R6 verb set every keyed collection carries, and a public name — it is a
part in the ADR-0035 sense (`PromptManager` composes it), so a leading
underscore is a false claim of module-privacy.
"""

from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext

# A per-turn provider: takes the active context, returns a string (or
# None/"" to emit nothing). Defined here — not in `prompt/manager.py` — so
# that module can import it without a circular import.
SimplePrompt = Callable[[AnyContext], "str | None"]


class LiveContextProviders:
    """Named dynamic providers, composed in registration order.

    Each provider is called every turn and its non-empty output is appended
    to the ``<live-context>`` block. A provider that raises must never take
    the prompt down with it, so each is called under a try/except and
    skipped — these are downstream extension points, and one bad plugin must
    not cost the whole prompt.
    """

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
        """Every provider's non-empty output, in registration order.

        A provider that raises is logged and skipped: these are downstream
        extension points, and one bad plugin must not cost the whole prompt.
        """
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
