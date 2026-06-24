from functools import lru_cache
from pathlib import Path
from typing import Callable

from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.util.markdown import make_markdown_section


def build_skill_replacements(
    skill_manager: SkillManager,
    active_skills: list[str] | None = None,
) -> dict[str, str]:
    """Compute the placeholder values mandate.md substitutes into its Skill
    Activation section, so the skill catalogue lives there instead of a separate
    ``claude_skills`` prompt section.

    Returns ``{CORE_SKILLS}``, ``{AVAILABLE_SKILLS}``, ``{ACTIVE_SKILLS}``:

    - ``CORE_SKILLS`` — the always-on methodology baseline (built-in skills
      under ``llm_plugin/core_skills/``), as a bullet list.
    - ``AVAILABLE_SKILLS`` — every other model-invocable skill (user, project,
      plugin), as a bullet list.
    - ``ACTIVE_SKILLS`` — full content of any pre-activated skills, loaded up
      front; empty when none. Active skills are dropped from the two lists above
      so the model is not told to activate something already loaded.
    """
    active = set(active_skills or [])
    core: list[Skill] = []
    other: list[Skill] = []
    for skill in skill_manager.get_skills():
        if not skill.model_invocable or skill.name in active:
            continue
        (core if _is_core_skill(skill) else other).append(skill)
    return {
        "CORE_SKILLS": _format_skill_list(core),
        "AVAILABLE_SKILLS": _format_skill_list(other) or "_(none registered)_",
        "ACTIVE_SKILLS": _format_active_skills(skill_manager, active_skills),
    }


def _is_core_skill(skill: Skill) -> bool:
    """A core skill is a built-in shipped under ``llm_plugin/core_skills/``."""
    return "core_skills" in Path(skill.path).parts


def _format_skill_list(skills: list[Skill]) -> str:
    return "\n".join(f"- **{s.name}** — {s.description}" for s in skills)


def _format_active_skills(
    skill_manager: SkillManager, active_skills: list[str] | None
) -> str:
    if not active_skills:
        return ""
    parts: list[str] = []
    for name in active_skills:
        skill = skill_manager.get_skill(name)
        if not (skill and skill.model_invocable):
            continue
        content = skill_manager.get_skill_content(name) or skill.description
        parts.append(make_markdown_section(name, content))
    return make_markdown_section("Active Skills (Fully Loaded)", "\n\n".join(parts))


def create_project_context_prompt():
    def project_context(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()

        doc_files: dict[str, list[Path]] = {
            "AGENTS.md": [],
            "CLAUDE.md": [],
            "GEMINI.md": [],
            "README.md": [],
        }

        for directory in search_dirs:
            for filename in doc_files.keys():
                file_path = directory / filename
                if file_path.exists() and file_path.is_file():
                    doc_files[filename].append(file_path)

        # Collect all found file paths, ordered least to most specific
        listed_files: list[str] = []
        for filename in doc_files.keys():
            for file_path in doc_files[filename]:
                listed_files.append(f"- `{file_path}`")

        if not listed_files:
            return next_handler(ctx, current_prompt)

        parts = [
            "### Documentation Files Found",
            "(See Operating Rules → Project Documentation for when to read these.)",
            *listed_files,
        ]

        context_message = "\n".join(parts)
        return next_handler(
            ctx,
            f"{current_prompt}\n\n{make_markdown_section('Project Documentation', context_message)}",
        )

    return project_context


def _get_search_directories() -> list[Path]:
    try:
        home_str = str(Path.home())
    except Exception:
        home_str = ""
    try:
        cwd_str = str(Path.cwd())
    except Exception:
        cwd_str = ""
    return [Path(p) for p in _get_search_directories_cached(home_str, cwd_str)]


@lru_cache(maxsize=8)
def _get_search_directories_cached(home_str: str, cwd_str: str) -> tuple[str, ...]:
    """Compute the project-doc search path once per (home, cwd) pair.

    Returned as a tuple of strings so the cache key/value are hashable. The
    walk is pure: walking the parent chain produces the same list every
    invocation in a session, so caching has no correctness risk.
    """
    dirs: list[str] = []
    if home_str:
        dirs.append(str(Path(home_str) / ".claude"))
    if cwd_str:
        cwd = Path(cwd_str)
        # Parents returns [parent, grandparent...]. We want reversed (Root first)
        # so specific configs (closer to CWD) override general ones.
        for parent in reversed(list(cwd.parents)):
            dirs.append(str(parent))
        dirs.append(str(cwd))
    return tuple(dirs)
