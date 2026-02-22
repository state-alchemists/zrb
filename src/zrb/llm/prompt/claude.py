import re
from pathlib import Path
from typing import Callable, List, Optional

from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.util.markdown import make_markdown_section


def create_claude_skills_prompt(
    skill_manager: SkillManager,
    active_skills: Optional[List[str]] = None,
    include_claude_skills: bool = True,
):
    def claude_compatibility(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()
        additional_context = []

        # 1. Available Claude Skills
        skills_section = _get_skills_section(
            skill_manager,
            search_dirs,
            active_skills=active_skills,
            include_claude_skills=include_claude_skills,
        )
        if skills_section:
            additional_context.append(skills_section)

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return claude_compatibility


def create_project_context_prompt():
    def project_context(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()
        project_docs = []
        found_files_paths = []

        for filename in ["CLAUDE.md", "AGENTS.md"]:
            content = _get_combined_content(filename, search_dirs)
            if content:
                summary = _summarize_markdown(content, max_len=5000)
                if summary == content:
                    doc_section = f"## Content of {filename}\n\n" f"{summary}"
                else:
                    doc_section = (
                        f"## Summary of {filename}\n"
                        "**Read the full file if you need to understand project-specific commands, conventions, or architecture.**\n"
                        "Failure to do so may result in incorrect implementations.\n\n"
                        f"{summary}"
                    )
                project_docs.append(doc_section)

            # Track found file paths for fallback message
            for directory in search_dirs:
                file_path = directory / filename
                if file_path.exists() and file_path.is_file():
                    found_files_paths.append(f"- `{file_path}`")
                    break

        if project_docs:
            # Content was found and summarized
            return next_handler(
                ctx,
                f"{current_prompt}\n\n{make_markdown_section('Project Documentation Summary', '\n\n'.join(project_docs))}",
            )
        elif found_files_paths:
            # Files were found but might be empty or content could not be processed
            context_message = (
                "The following project documentation files are available. "
                "You MUST ALWAYS `Read` them if you need to understand "
                "project conventions, architectural patterns, or specific guidelines. "
                "NEVER assume project structure without verifying these files:\n"
                + "\n".join(found_files_paths)
            )
            return next_handler(
                ctx,
                f"{current_prompt}\n\n{make_markdown_section('Project Documentation', context_message)}",
            )
        else:
            # No documentation found
            return next_handler(ctx, current_prompt)

    return project_context


def _summarize_markdown(
    content: str, max_len: int = 10000, snippet_len: int = 1000
) -> str:
    if len(content) <= max_len:
        return content

    summary = []
    total_length = 0

    # Regex to find markdown headers
    header_pattern = re.compile(r"(^|\n)(#+)\s+(.*)")
    matches = list(header_pattern.finditer(content))

    if not matches:
        # If no headers, just truncate the whole content
        return content[:max_len] + "... (more)" if len(content) > max_len else content

    for i, match in enumerate(matches):
        header = match.group(0).strip()
        summary.append(header)
        total_length += len(header)

        # Get the content between this header and the next
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        snippet = content[start_pos:end_pos].strip()

        if snippet:
            if len(snippet) > snippet_len:
                snippet = snippet[:snippet_len].strip() + "... (more)"
            summary.append(snippet)
            total_length += len(snippet)

        if total_length > max_len:
            break

    return "\n\n".join(summary)[:max_len]


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
    skill_manager: SkillManager,
    search_dirs: list[Path],
    active_skills: Optional[List[str]] = None,
    include_claude_skills: bool = True,
) -> Optional[str]:
    # Use SkillManager's built-in search directories logic
    skills = skill_manager.scan(search_dirs=skill_manager.get_search_directories())
    if not skills:
        return None

    skills_context = []

    # Add active skills first (if any) with their full content
    if active_skills:
        skills_context.append("## Active Skills (Fully Loaded)")
        for skill_name in active_skills:
            skill_obj = skill_manager.get_skill(skill_name)

            if skill_obj and skill_obj.model_invocable:
                if not include_claude_skills and not skill_name.startswith(
                    "core_mandate_"
                ):
                    continue
                # Get the full skill content
                skill_content = skill_manager.get_skill_content(skill_name)
                if skill_content:
                    skills_context.append(f"### {skill_name}")
                    skills_context.append(skill_content)
                else:
                    # Fallback to description if content can't be loaded
                    skills_context.append(f"- {skill_name}: {skill_obj.description}")
        skills_context.append("")  # Add empty line for separation

    # Add available skills (just metadata)
    skills_context.append("## Available Skills")
    skills_context.append(
        "You MUST ALWAYS use 'ActivateSkill' to load instructions for a skill before execution."
    )
    for skill in skills:
        if skill.model_invocable:
            if not include_claude_skills and not skill.name.startswith("core_mandate_"):
                continue
            # Skip skills that are already active
            if active_skills and skill.name in active_skills:
                continue
            skills_context.append(f"- {skill.name}: {skill.description}")

    return make_markdown_section(
        "Available Skills (Claude Skills)", "\n".join(skills_context)
    )
