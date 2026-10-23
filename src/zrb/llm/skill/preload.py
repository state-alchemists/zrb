"""Resolve the `preload:` skills a skill declares.

A preloaded skill renders in the same response as the skill that names it, so
the model does not spend a round trip activating it. The declaration is about
content, not permission: an unknown or user-only name is reported and skipped,
and the activating skill still works.
"""

from __future__ import annotations

from zrb.llm.skill.manager import Skill, SkillManager

#: Deepest preload chain rendered. Three covers a methodology plus its
#: sub-methodology without letting one declaration pull in the whole catalogue.
MAX_PRELOAD_DEPTH = 3


def format_preload_problems(problems: list[str]) -> str:
    """One actionable line for a declaration that did not fully resolve."""
    return (
        "[SYSTEM SUGGESTION]: this skill's `preload` did not resolve: "
        + "; ".join(problems)
        + ". The skill itself is active; carry on without the missing context, "
        "and fix the declaration when you next touch the file."
    )


def resolve_preload(
    skill_manager: SkillManager,
    skill: Skill,
    max_depth: int = MAX_PRELOAD_DEPTH,
) -> tuple[list[Skill], list[str]]:
    """Return ``(skills to render, problems)``, deepest dependency first.

    Duplicates and the root skill are dropped. A cycle, an unknown name, a
    user-invocable-only skill, or a chain past *max_depth* becomes a problem
    string instead of an error.
    """
    resolved: list[Skill] = []
    problems: list[str] = []
    seen = {skill.name}
    _collect(skill_manager, skill, 1, max_depth, seen, resolved, problems)
    return resolved, problems


def _collect(
    skill_manager: SkillManager,
    skill: Skill,
    depth: int,
    max_depth: int,
    seen: set[str],
    resolved: list[Skill],
    problems: list[str],
) -> None:
    preload = getattr(skill, "preload", [])
    if not isinstance(preload, list):
        return
    for name in preload:
        if name in seen:
            problems.append(f"'{name}' is already loaded (cycle or duplicate)")
            continue
        if depth > max_depth:
            problems.append(f"'{name}' is deeper than max_preload_depth={max_depth}")
            continue
        found = skill_manager.get_skill(name)
        if found is None:
            problems.append(f"'{name}' is not a registered skill")
            continue
        if not found.model_invocable:
            problems.append(f"'{name}' is user-invocable only")
            continue
        seen.add(name)
        _collect(skill_manager, found, depth + 1, max_depth, seen, resolved, problems)
        resolved.append(found)
