"""`SkillRegistry` — the canonical collection of skills (ADR-0090).

Discovered skills plus everything registered in code; `SkillManager` does the
scanning. Layer and allowlist semantics are `LayeredRegistry`'s; the allowlist
here is ``CFG.LLM_SKILLS``. Configure it from `zrb_init.py`:

    from zrb.llm.skill.registry import skill_registry
    from zrb.llm.skill.manager import Skill
    skill_registry.add_skill(Skill(name="mine", path=".", description="..."))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from zrb.config.config import CFG
from zrb.llm.util.layered_registry import LayeredRegistry

if TYPE_CHECKING:
    from zrb.llm.skill.manager import Skill

SkillSetValue = list["Skill"] | Callable[[], list["Skill"]]


class SkillRegistry:
    """The canonical collection of skills, and the source of defaults."""

    def __init__(self, skills: SkillSetValue | None = None):
        """Create a registry, optionally seeded with *skills*.

        Args:
            skills: Initial manual layer; a plain list freezes at set time, a
                callable stays deferred until each query.
        """
        self._layers: LayeredRegistry[Skill] = LayeredRegistry(
            lambda: CFG.LLM_SKILLS, skills
        )

    def add_skill(self, skill: "Skill") -> None:
        """Register a skill manually; it survives a later scan or reload."""
        self._layers.add_item(skill)

    def remove_skill(self, name: str) -> None:
        """Drop *name* from both the manual and discovered layers."""
        self._layers.remove_item(name)

    def set_skills(self, skills: SkillSetValue) -> None:
        """Replace the manual layer; a callable is re-evaluated at each query."""
        self._layers.set_items(skills)

    def set_discovered(self, skills: list["Skill"]) -> None:
        """Replace the discovered layer (used by `SkillManager.scan`)."""
        self._layers.set_discovered(skills)

    def clear_discovered(self) -> None:
        """Drop the discovered layer, keeping manual registrations."""
        self._layers.clear_discovered()

    def get_skill(self, name: str) -> "Skill | None":
        """Look up one visible entry by registered name, own name, or path."""
        return self._layers.get_item(name)

    def get_skills(self) -> list["Skill"]:
        """Every visible entry; manual wins on collisions."""
        return self._layers.get_items()


skill_registry = SkillRegistry()
