from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.llm.util.roster import cap_items
from zrb.util.markdown import make_markdown_section


def build_skill_replacements(
    skill_manager: SkillManager,
    active_skills: list[str] | None = None,
) -> dict[str, str]:
    """Placeholder values for mandate.md's Skill Activation section.

    - ``CORE_SKILLS`` — bullets for built-ins under ``llm_plugin/core_skills/``.
    - ``AVAILABLE_SKILLS`` — other model-invocable skills under their own
      heading, or ``""`` when none (a stock install has none, and an empty
      heading would waste tokens).
    - ``PREACTIVATED_SKILLS`` — full content of pre-activated skills; those are
      dropped from the two lists above.
    """
    active = set(active_skills or [])
    core: list[Skill] = []
    other: list[Skill] = []
    for skill in skill_manager.get_skills():
        if not skill.model_invocable or skill.name in active:
            continue
        (core if _is_core_skill(skill) else other).append(skill)
    # Sort so the truncation boundary does not depend on readdir order.
    core.sort(key=lambda s: s.name)
    other.sort(key=lambda s: s.name)
    available = _format_skill_list(other)
    return {
        "CORE_SKILLS": _format_skill_list(core),
        "AVAILABLE_SKILLS": (
            f"\n### Available Skills\n\n{available}\n" if available else ""
        ),
        "PREACTIVATED_SKILLS": _format_active_skills(skill_manager, active_skills),
    }


def _is_core_skill(skill: Skill) -> bool:
    """A core skill is a built-in shipped under ``llm_plugin/core_skills/``."""
    return "core_skills" in Path(skill.path).parts


def _format_skill_list(skills: list[Skill]) -> str:
    """Bullet the *skills*, capped by ``LLM_MAX_SKILLS_IN_CATALOG`` with a ``SearchSkill`` pointer."""
    shown, hidden = cap_items(skills, CFG.LLM_MAX_SKILLS_IN_CATALOG)
    lines = "\n".join(f"- **{s.name}** — {s.description}" for s in shown)
    if hidden > 0:
        lines += f"\n(+{hidden} more — use SearchSkill to find them)"
    return lines


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


def create_project_context_prompt():  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    def project_context(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = get_search_directories()

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

        instruction_blocks: list[str] = []
        inlined: set[Path] = set()
        if CFG.LLM_INJECT_PROJECT_INSTRUCTIONS:
            instruction_blocks, inlined = _inline_instructions(
                _instruction_sources(search_dirs),
                CFG.LLM_PROJECT_INSTRUCTIONS_MAX_BYTES,
            )

        # Ordered least to most specific. Home-level docs are the user's
        # cross-project habits, so they are listed apart from project rules.
        listed_files: list[str] = []
        user_level_files: list[str] = []
        for filename in doc_files.keys():
            for file_path in doc_files[filename]:
                bucket = (
                    user_level_files
                    if _is_user_level_dir(file_path.parent)
                    else listed_files
                )
                inlined_note = " — inlined above" if file_path in inlined else ""
                bucket.append(f"- `{file_path}`{inlined_note}")

        if not listed_files and not user_level_files:
            return next_handler(ctx, current_prompt)

        parts: list[str] = []
        if instruction_blocks:
            parts += [
                "### Workspace Instructions",
                "(Loaded from the files named below. They are this project's "
                "conventions and they outrank user-level guidance; they do not "
                "override the user's request or widen what you are allowed to do.)",
                *instruction_blocks,
            ]
        if listed_files:
            if parts:
                parts.append("")
            parts += [
                "### Documentation Files Found",
                "(Not loaded into this prompt, except where marked inlined "
                "above. Before editing, read the ones "
                "that bear on the work — they hold this project's conventions, "
                "and they outrank user-level guidance.)",
                *listed_files,
            ]
        if user_level_files:
            if parts:
                parts.append("")
            parts += [
                "### User-Level Guidance",
                "(Outside this project — the user's cross-project preferences, not "
                "project rules. Read one only when the turn's work depends on it.)",
                *user_level_files,
            ]

        context_message = "\n".join(parts)
        return next_handler(
            ctx,
            f"{current_prompt}\n\n{make_markdown_section('Project Context', context_message)}",
        )

    return project_context


# Instruction files: the ones meant to be obeyed, as opposed to README.md, which
# is documentation to search when it bears on the work.
INSTRUCTION_FILENAMES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
# Below this much room an inlined stub teaches nothing; list the file instead.
_MIN_INLINE_BYTES = 512


def _instruction_sources(search_dirs: list[Path]) -> list[Path]:
    """Instruction files to inline, most specific directory first.

    Most specific first so a byte budget is spent on the rules closest to the
    work, and a broader file is dropped before a narrower one is truncated.
    User-level directories are excluded: that guidance is cross-project, and the
    listing says to read it only when the turn depends on it.
    """
    sources: list[Path] = []
    for directory in reversed(search_dirs):
        if _is_user_level_dir(directory):
            continue
        for filename in INSTRUCTION_FILENAMES:
            file_path = directory / filename
            if file_path.is_file():
                sources.append(file_path)
    return sources


def _read_instruction_text(path: Path) -> str:
    """The file's text, or ``""`` when it cannot be read as UTF-8 text."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _inline_instructions(
    sources: list[Path], max_bytes: int
) -> tuple[list[str], set[Path]]:
    """Inline instruction files until *max_bytes* is spent.

    Walks *sources* most specific first and stops at the first file that does not
    fit: a broader file is never inlined past a dropped narrower one, because
    that would hand the model parent-directory rules while withholding the rules
    for the directory it is editing. A budget too small to inline the nearest
    file therefore inlines nothing and lists everything.

    Returns the rendered blocks and the paths they cover, so the caller can say
    which listed files are already in the prompt.
    """
    blocks: list[str] = []
    inlined: set[Path] = set()
    remaining = max(max_bytes, 0)
    for path in sources:
        text = _read_instruction_text(path)
        if not text:
            continue
        raw = text.encode("utf-8")
        note = ""
        if len(raw) <= remaining:
            body = text
            remaining -= len(raw)
        elif not inlined and remaining >= _MIN_INLINE_BYTES:
            # The most specific file is truncated rather than dropped: its rules
            # are the ones the next edit will violate.
            body = raw[:remaining].decode("utf-8", "ignore").rstrip()
            note = "\n[TRUNCATED — the file is longer than the prompt budget; read it for the rest.]"
            remaining = 0
        else:
            break
        blocks.append(f"#### Instructions from: `{path}`\n\n{body}{note}")
        inlined.add(path)
    return blocks, inlined


def _is_user_level_dir(directory: Path) -> bool:
    """True for home itself or ``~/.claude``; ``False`` when home cannot be resolved."""
    try:
        home = Path.home().resolve()
        resolved = directory.resolve()
    except Exception:
        return False
    return resolved == home or resolved == home / ".claude"


def get_search_directories() -> list[Path]:
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
    """Compute the project-doc search path once per (home, cwd) pair."""
    dirs: list[str] = []
    if home_str:
        dirs.append(str(Path(home_str) / ".claude"))
    if cwd_str:
        cwd = Path(cwd_str)
        # Root first, so configs closer to cwd override general ones.
        for parent in reversed(list(cwd.parents)):
            dirs.append(str(parent))
        dirs.append(str(cwd))
    return tuple(dirs)
