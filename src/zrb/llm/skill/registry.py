"""`SkillRegistry` — the canonical collection of skills.

Per ADR-0090, a registry is the *source of defaults*: it stores the full set of
skills found by filesystem discovery *plus* everything appended in code,
and answers queries. It does not scan or resolve — that is `SkillManager`'s
job. Configure it from `zrb_init.py`:

    from zrb.llm.skill.registry import skill_registry
    from zrb.llm.skill.manager import Skill
    skill_registry.add_skill(Skill(name="mine", path=".", description="..."))

A manually-added skill always survives a later `scan()`/`reload()` — the
scan refreshes only the discovered layer, and a manual registration wins a
name collision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.skill.manager import Skill

# `set_skills` accepts either a concrete collection or a deferred callable
# producing one. A callable is resolved at query time (ADR-0090 Part 3), so a
# value set during `zrb_init.py` honors later `CFG`/registry changes instead
# of freezing at assignment.
SkillSetValue = list["Skill"] | Callable[[], list["Skill"]]


class SkillRegistry:
    """The canonical collection of skills, and the source of defaults.

    The registry keeps two layers so a scan cannot wipe a registration:

    - *manual* — skills registered from code (`add_skill`, `set_skills`);
      always wins a name collision.
    - *discovered* — skills found on disk by `SkillManager.scan()`; a later
      scan replaces this layer only.

    Queries merge the two, manual first. `set_skills` replaces the whole
    collection (the clean-slate swap); `remove_skill` drops a name from both
    layers.
    """

    def __init__(self, skills: list["Skill"] | None = None):
        """Create a skill registry, optionally seeded with *skills*.

        Args:
            skills: Initial manual layer. May be regenerated later with
                `set_skills`; a plain list freezes at set time, while a
                callable stays deferred until the first query.
        """
        self._manual: SkillSetValue = []
        self._discovered: dict[str, Skill] = {}
        if skills is not None:
            self.set_skills(skills)

    def _resolve(self, value: SkillSetValue) -> list["Skill"]:
        return value() if callable(value) else value

    def _effective_manual(self) -> dict[str, Skill]:
        resolved = self._resolve(self._manual)
        return {skill.name: skill for skill in resolved}

    def _resolved_view(self) -> tuple[dict[str, Skill], dict[str, Skill]]:
        """Resolve the manual layer exactly once; return ``(manual, merged)``.

        A deferred manual value (`set_skills(lambda ...)`) is re-evaluated per
        query — but once per query, not once per member: both the merged
        collection and the visibility check must come from the same resolution,
        or a stateful supplier could be filtered against a different snapshot
        than the one merged.
        """
        manual = self._effective_manual()
        merged = dict(self._discovered)
        merged.update(manual)
        return manual, merged

    def add_skill(self, skill: "Skill") -> None:
        """Register *skill* manually. Survives a later scan or reload.

        If the manual layer was set with a deferred callable, the callable is
        resolved once and the skill appended, freezing the default in place.
        """
        self._manual = [*self._resolve(self._manual), skill]

    def remove_skill(self, name: str) -> None:
        """Drop *name* from both the manual and discovered layers."""
        self._manual = [s for s in self._resolve(self._manual) if s.name != name]
        self._discovered.pop(name, None)

    def set_skills(self, skills: SkillSetValue) -> None:
        """Replace the whole collection (manual layer) with *skills*.

        *skills* may be a list or a deferred callable returning one. A callable
        stays unresolved and is re-evaluated at each query,
        so a value set during `zrb_init.py` honors later `CFG`/registry changes.
        """
        self._manual = skills

    def set_discovered(self, skills: list["Skill"]) -> None:
        """Replace the discovered layer (used by `SkillManager.scan`).

        Later entries win a name collision, preserving the scan's
        global→project precedence. Manual registrations are untouched.
        """
        self._discovered = {skill.name: skill for skill in skills}

    def clear_discovered(self) -> None:
        """Drop the discovered layer, keeping manual registrations."""
        self._discovered = {}

    def get_skill(self, name: str) -> "Skill | None":
        """Look up one skill by registered name, own name, or path."""
        manual, effective = self._resolved_view()
        skill = effective.get(name)
        if not skill:
            for candidate in effective.values():
                if candidate.name == name or candidate.path == name:
                    skill = candidate
                    break
        if skill and not self._is_visible(skill.name, manual):
            return None
        return skill

    def get_skills(self) -> list["Skill"]:
        """Every visible skill in the effective collection, manual wins on
        collisions. The ``CFG.LLM_SKILLS`` allowlist twin filters only the
        discovered layer; skills registered manually (`add_skill`,
        `set_skills`) are always visible."""
        manual, effective = self._resolved_view()
        return [
            skill
            for skill in effective.values()
            if self._is_visible(skill.name, manual)
        ]

    def _is_visible(self, name: str, manual: dict[str, Skill]) -> bool:
        """Whether *name* survives the ``LLM_SKILLS`` allowlist twin.

        The twin (ADR-0091) is a coarse filter over the *discovered* layer:
        env names the default skills that stay visible. Anything registered
        manually layers on top and is always visible, matching the mental
        model "env sets the baseline; `zrb_init.py` builds on it". The
        registry reads ``CFG`` lazily at query time, so env changes take
        effect on the next catalogue lookup without any startup copy.
        *manual* is the already-resolved manual layer from the caller's
        single per-query resolution.
        """
        if name in manual:
            return True
        allowed = list(CFG.LLM_SKILLS or [])
        return not allowed or name in allowed


skill_registry = SkillRegistry()
