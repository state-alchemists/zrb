"""`LayeredRegistry` — the two-layer collection behind the skill and sub-agent
registries (ADR-0090).

A registry is the *source of defaults*: it stores everything found by
filesystem discovery plus everything registered in code, and answers queries.
It does not scan — that is the owning manager's job.

- *manual* — items registered from code; always wins a name collision and
  survives a later scan. May be a deferred callable, resolved at query time
  (ADR-0090 Part 3), so a value set during `zrb_init.py` honors later
  `CFG`/registry changes.
- *discovered* — items found on disk; a scan replaces this layer only.

An allowlist (ADR-0091) filters only the discovered layer; manual
registrations are always visible ("env sets the baseline; `zrb_init.py`
builds on it"). It is read at query time, so env changes apply on the next
lookup.
"""

from __future__ import annotations

from typing import Callable, Generic, Protocol, TypeVar


class RegistryItem(Protocol):
    name: str
    path: str


T = TypeVar("T", bound=RegistryItem)


class LayeredRegistry(Generic[T]):
    """Manual + discovered layers, merged manual-first on every query."""

    def __init__(
        self,
        get_allowlist: Callable[[], list[str] | None],
        items: list[T] | Callable[[], list[T]] | None = None,
    ):
        """Create a registry, optionally seeded with *items*.

        Args:
            get_allowlist: Returns the names discovered items must appear in to
                be visible; empty or `None` allows all.
            items: Initial manual layer; a plain list freezes at set time,
                a callable stays deferred until each query.
        """
        self._get_allowlist = get_allowlist
        self._manual: list[T] | Callable[[], list[T]] = []
        self._discovered: dict[str, T] = {}
        if items is not None:
            self.set_items(items)

    def add_item(self, item: T) -> None:
        """Register *item* manually. A deferred manual layer is resolved once
        and the item appended, freezing it in place."""
        self._manual = [*self._resolve(self._manual), item]

    def remove_item(self, name: str) -> None:
        """Drop *name* from both layers."""
        self._manual = [i for i in self._resolve(self._manual) if i.name != name]
        self._discovered.pop(name, None)

    def set_items(self, items: list[T] | Callable[[], list[T]]) -> None:
        """Replace the whole manual layer — the clean-slate swap."""
        self._manual = items

    def set_discovered(self, items: list[T]) -> None:
        """Replace the discovered layer. Later entries win a name collision,
        preserving the scan's global→project precedence."""
        self._discovered = {item.name: item for item in items}

    def clear_discovered(self) -> None:
        """Drop the discovered layer, keeping manual registrations."""
        self._discovered = {}

    def get_item(self, name: str) -> T | None:
        """Look up one visible item by registered name, own name, or path."""
        manual, effective = self._resolved_view()
        item = effective.get(name)
        if not item:
            item = next(
                (c for c in effective.values() if name in (c.name, c.path)), None
            )
        if item and not self._is_visible(item.name, manual):
            return None
        return item

    def get_items(self) -> list[T]:
        """Every visible item; manual wins on collisions."""
        manual, effective = self._resolved_view()
        return [i for i in effective.values() if self._is_visible(i.name, manual)]

    def _resolve(self, value: list[T] | Callable[[], list[T]]) -> list[T]:
        return value() if callable(value) else value

    def _resolved_view(self) -> tuple[dict[str, T], dict[str, T]]:
        """Resolve the manual layer once per query; return ``(manual, merged)``.

        Merging and the visibility check must see the same resolution, or a
        stateful supplier could be filtered against a different snapshot.
        """
        manual = {item.name: item for item in self._resolve(self._manual)}
        return manual, {**self._discovered, **manual}

    def _is_visible(self, name: str, manual: dict[str, T]) -> bool:
        if name in manual:
            return True
        allowed = list(self._get_allowlist() or [])
        return not allowed or name in allowed
