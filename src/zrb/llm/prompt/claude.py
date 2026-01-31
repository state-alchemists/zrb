from pathlib import Path
from typing import Callable

from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import SkillManager
from zrb.util.markdown import make_markdown_section


def create_claude_skills_prompt(skill_manager: SkillManager):
    def claude_compatibility(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()
        additional_context = []

        # 1. CLAUDE.md
        claude_content = _get_combined_content("CLAUDE.md", search_dirs)
        if claude_content:
            additional_context.append(
                make_markdown_section(
                    "Project Instructions (CLAUDE.md)", claude_content
                )
            )

        # 2. AGENTS.md
        agents_content = _get_combined_content("AGENTS.md", search_dirs)
        if agents_content:
            additional_context.append(
                make_markdown_section("Agent Definitions (AGENTS.md)", agents_content)
            )

        # 3. Available Claude Skills
        skills_section = _get_skills_section(skill_manager, search_dirs)
        if skills_section:
            additional_context.append(skills_section)

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return claude_compatibility


def _get_search_directories() -> list[Path]:
    search_dirs: list[Path] = []
    # 1. User global config (~/.claude)
    try:
        home = Path.home()
        search_dirs.append(home / ".claude")
    except Exception:
        pass

    # 2. Project directories (Root -> ... -> CWD)
    try:
        cwd = Path.cwd()
        # Parents returns [parent, grandparent...]. We want reversed (Root first)
        # This allows specific configs (closer to CWD) to override general ones
        project_dirs = list(cwd.parents)[::-1] + [cwd]
        search_dirs.extend(project_dirs)
    except Exception:
        pass
    return search_dirs


def _get_combined_content(filename: str, search_dirs: list[Path]) -> str:
    contents = []
    for directory in search_dirs:
        file_path = directory / filename
        if file_path.exists() and file_path.is_file():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        contents.append(content)
            except Exception:
                pass
    return "\n\n".join(contents)


def _get_skills_section(
    skill_manager: SkillManager, search_dirs: list[Path]
) -> str | None:
    # Use SkillManager's built-in search directories logic
    skills = skill_manager.scan(search_dirs=skill_manager.get_search_directories())
    if not skills:
        return None

    skills_context = ["Use 'activate_skill' to load instructions for a skill."]
    for skill in skills:
        if skill.model_invocable:
            skills_context.append(f"- {skill.name}: {skill.description}")

    return make_markdown_section(
        "Available Skills (Claude Skills)", "\n".join(skills_context)
    )
