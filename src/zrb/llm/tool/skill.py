from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.skill.activation import build_activation_block
from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as default_skill_manager
from zrb.llm.skill.preload import format_preload_problems, resolve_preload
from zrb.llm.util.roster import cap_items, search_roster


def create_activate_skill_tool(skill_manager: SkillManager | None = None):
    if skill_manager is None:
        skill_manager = default_skill_manager

    async def activate_skill_impl(
        skill: Annotated[
            str,
            Field(
                description=(
                    "An exact skill name, e.g. 'core-coding'. A name that does "
                    "not resolve comes back with the valid ones listed — do "
                    "not guess twice."
                )
            ),
        ],
    ) -> str:
        found = skill_manager.get_skill(skill)

        if not found:
            return _skill_not_found_message(skill, skill_manager)

        if not found.model_invocable:
            return (
                f"Skill '{skill}' is not invocable by the model. "
                "[SYSTEM SUGGESTION]: it is a user-facing command, not an "
                "agent skill — carry out the work yourself. "
                + _available_skills_hint(skill_manager)
            )

        content = skill_manager.get_skill_content(skill)
        if not content:
            return _skill_not_found_message(skill, skill_manager)

        preloaded, problems = resolve_preload(skill_manager, found)
        blocks = [
            build_activation_block(
                dependency,
                skill_manager.get_skill_content(dependency.name)
                or dependency.description,
                preloaded_by=found.name,
            )
            for dependency in preloaded
        ]
        blocks.append(build_activation_block(found, content, announce=True))
        if problems:
            blocks.append(format_preload_problems(problems))
        return "\n\n".join(blocks)

    activate_skill_impl.__name__ = "ActivateSkill"
    # No roster here: the prompt's skill catalogue already lists the names, and
    # a pointer to that section would dangle when it is toggled off. An unknown
    # name gets the valid ones in its error instead.
    activate_skill_impl.__doc__ = (
        "Activates specialized expertise from a skill.\n\n"
        "Returns the skill's full content, its directory path, and a listing of any\n"
        "companion files (scripts, docs, data). Use Read/Glob on the directory to\n"
        "access companion files referenced in the skill content."
    )
    return activate_skill_impl


def create_search_skill_tool(skill_manager: SkillManager | None = None):
    if skill_manager is None:
        skill_manager = default_skill_manager

    async def search_skill(
        query: Annotated[
            str,
            Field(
                description=(
                    "Words to match against skill names and descriptions "
                    "(case-insensitive). Leave empty to list activatable "
                    "skills unfiltered; the listing caps at 30 matches — "
                    "narrow the query for the rest."
                )
            ),
        ] = "",
    ) -> str:
        skills = [s for s in skill_manager.get_skills() if s.model_invocable]
        return search_roster(skills, query) or _no_skill_match_message(query)

    search_skill.__name__ = "SearchSkill"
    # No roster or cap value here: the docstring ships on every request.
    search_skill.__doc__ = (
        "Searches the skill catalogue by name or description.\n\n"
        "Use it when the prompt's skill list is truncated, or a skill you need "
        "is not listed."
    )
    return search_skill


def _no_skill_match_message(query: str) -> str:
    """Text for an empty search result."""
    if query.strip():
        return (
            f"No skills match '{query.strip()}'. [SYSTEM SUGGESTION]: retry with "
            "broader terms — matching covers skill names and descriptions."
        )
    return "No activatable skills are registered."


def _available_skills_hint(skill_manager: SkillManager) -> str:
    """The valid `skill` values, capped by ``LLM_MAX_SKILLS_IN_CATALOG``."""
    names = sorted(s.name for s in skill_manager.get_skills() if s.model_invocable)
    if not names:
        return "No activatable skills are registered."
    shown, hidden = cap_items(names, CFG.LLM_MAX_SKILLS_IN_CATALOG)
    hint = ", ".join(shown)
    if hidden > 0:
        hint += f", and {hidden} more (use SearchSkill to list them)"
    return f"Activatable skills are: {hint}."


def _skill_not_found_message(skill: str, skill_manager: SkillManager) -> str:
    """Not-found error that lists the valid skills (mirrors ``agent_not_found_message``)."""
    return f"Skill '{skill}' not found. [SYSTEM SUGGESTION]: " + _available_skills_hint(
        skill_manager
    )
