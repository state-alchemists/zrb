from pathlib import Path

from zrb.config.config import CFG
from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as default_skill_manager
from zrb.llm.skill.util import discover_companion_files, format_companion_file_lines

# On-demand search results are themselves capped so an unscoped query (or an
# empty one) cannot dump the whole catalogue in one answer. 30 entries keeps a
# full page of matches visible while still bounding a runaway listing.
_SEARCH_RESULT_LIMIT = 30


def create_activate_skill_tool(skill_manager: SkillManager | None = None):
    if skill_manager is None:
        skill_manager = default_skill_manager

    async def activate_skill_impl(skill: str) -> str:
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

        skill_dir = str(Path(found.path).parent)
        companion_files = found.companion_files or discover_companion_files(found.path)

        header_lines = [
            "Skill activated. The following context applies:",
            "",
            f"Skill directory (working directory): {skill_dir}",
            "",
            "All file paths in the skill instructions below are relative to this directory.",
            "Use companion files (scripts, tools, references) by resolving them against this path.",
        ]
        header_lines.extend(format_companion_file_lines(companion_files))
        header_lines.append("")
        header_lines.append("---")

        header = "\n".join(header_lines)
        return f"<ACTIVATED_SKILL>\n{header}\n\n{content}\n</ACTIVATED_SKILL>"

    activate_skill_impl.__name__ = "ActivateSkill"
    # The roster is deliberately NOT embedded here: unlike DelegateToAgent's
    # agent list, it is already spelled out in the prompt's skill catalogue, and
    # duplicating it would pay for the same names twice on every request. The
    # docstring must not point *at* that catalogue either — sections toggle
    # independently, so a pointer dangles the moment one is trimmed. An unknown
    # name therefore resolves itself: the error lists the valid ones.
    activate_skill_impl.__doc__ = (
        "Activates specialized expertise from a skill.\n\n"
        "Returns the skill's full content, its directory path, and a listing of any\n"
        "companion files (scripts, docs, data). Use Read/Glob on the directory to\n"
        "access companion files referenced in the skill content.\n\n"
        "skill: an exact skill name, e.g. 'core-coding'. A name that does not\n"
        "resolve comes back with the valid ones listed — do not guess twice."
    )
    return activate_skill_impl


def create_search_skill_tool(skill_manager: SkillManager | None = None):
    if skill_manager is None:
        skill_manager = default_skill_manager

    async def search_skill(query: str = "") -> str:
        skills = [s for s in skill_manager.get_skills() if s.model_invocable]
        needle = query.strip().lower()
        if needle:
            skills = [
                s
                for s in skills
                if needle in s.name.lower() or needle in (s.description or "").lower()
            ]
        if not skills:
            return _no_skill_match_message(query)
        shown = skills[:_SEARCH_RESULT_LIMIT]
        lines = [f"- `{s.name}`: {s.description}" for s in shown]
        hidden = len(skills) - len(shown)
        if hidden > 0:
            lines.append(f"(+{hidden} more match — refine the query)")
        return "\n".join(lines)

    search_skill.__name__ = "SearchSkill"
    # The roster is deliberately NOT embedded here (mirrors ActivateSkill): the
    # catalogue is spelled out in the prompt, and this tool is the on-demand
    # window onto the part the prompt truncates. Naming the truncation cap here
    # would pin a config value into a docstring that ships on every request.
    search_skill.__doc__ = (
        "Searches the skill catalogue by name or description.\n\n"
        "Use it when the prompt's skill list is truncated, or a skill you need "
        "is not listed.\n\n"
        "query: words to match against skill names and descriptions "
        "(case-insensitive). Leave empty to list activatable skills unfiltered; "
        "the listing caps at 30 matches — narrow the query for the rest."
    )
    return search_skill


def _no_skill_match_message(query: str) -> str:
    """Text for an empty search result, naming the way back."""
    if query.strip():
        return (
            f"No skills match '{query.strip()}'. [SYSTEM SUGGESTION]: retry with "
            "broader terms — matching covers skill names and descriptions."
        )
    return "No activatable skills are registered."


def _available_skills_hint(skill_manager: SkillManager) -> str:
    """The valid `skill` values, for an error the model has to recover from.

    Capped by ``LLM_MAX_SKILLS_IN_CATALOG``: the error names a working subset
    and points at ``SearchSkill`` for the rest instead of dumping a huge
    roster into every retry.
    """
    names = sorted(s.name for s in skill_manager.get_skills() if s.model_invocable)
    if not names:
        return "No activatable skills are registered."
    cap = CFG.LLM_MAX_SKILLS_IN_CATALOG
    shown = names if cap < 1 else names[:cap]
    hint = ", ".join(shown)
    hidden = len(names) - len(shown)
    if hidden > 0:
        hint += f", and {hidden} more (use SearchSkill to list them)"
    return f"Activatable skills are: {hint}."


def _skill_not_found_message(skill: str, skill_manager: SkillManager) -> str:
    """Name the valid skills rather than telling the model to look them up.

    Mirrors ``agent_not_found_message`` for delegation: the usual failure is a
    misremembered name, so listing the real ones turns the retry into a
    correction instead of another guess.
    """
    return f"Skill '{skill}' not found. [SYSTEM SUGGESTION]: " + _available_skills_hint(
        skill_manager
    )
