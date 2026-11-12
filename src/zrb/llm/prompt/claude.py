import os
import re
import stat
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.llm.util.prompt import get_path_references
from zrb.llm.util.roster import cap_items
from zrb.util.dir_search import split_config_dir_patterns
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
        pointers: dict[Path, Path] = {}
        if CFG.LLM_INJECT_PROJECT_INSTRUCTIONS_ENABLED:
            instruction_blocks, inlined, pointers = _inline_instructions(
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
                bucket.append(
                    f"- `{file_path}`{_listing_note(file_path, inlined, pointers)}"
                )

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

# How many pointer files a chain may cross before it counts as unresolved.
# A chain that long is a broken layout, not a route to rules — and following it
# recursively once took prompt composition down with a `RecursionError` on a
# tree of a thousand nested `CLAUDE.md` files. Treating it as unresolved keeps
# the pointer inlined, which costs a line and never loses the only route.
MAX_POINTER_DEPTH = 16


def _instruction_sources(search_dirs: list[Path]) -> list[Path]:
    """Instruction files to inline, most specific directory first.

    Most specific first so a byte budget is spent on the rules closest to the
    work, and a broader file is dropped before a narrower one is truncated.
    User-level directories are excluded: that guidance is cross-project, and the
    listing says to read it only when the turn depends on it.

    A symlink is never a source. The link can name any readable file on the
    machine — `AGENTS.md -> ~/.ssh/id_rsa` is the shape of it — and whatever it
    names would be inlined into the system prompt and sent to the model provider
    before the user has seen it. It stays in the listing, so opening it is still
    a deliberate act, but nothing reads it on the user's behalf.
    """
    sources: list[Path] = []
    for directory in reversed(search_dirs):
        if _is_user_level_dir(directory):
            continue
        for filename in INSTRUCTION_FILENAMES:
            file_path = directory / filename
            if file_path.is_symlink():
                continue
            if file_path.is_file():
                sources.append(file_path)
    return sources


def _read_instruction_bytes(path: Path, max_bytes: int) -> bytes:
    """At most *max_bytes* + 1 bytes of the file, or ``b""`` when it cannot be read.

    The read is bounded, not the whole file: the budget is the most any one file
    may contribute, so bytes past it can never reach the prompt and reading them
    first would let a large or hostile instruction file exhaust memory before
    the budget was ever consulted. One byte over is enough to tell "fits" from
    "is longer" — which is all the walk needs to know.

    The descriptor is opened with ``O_NOFOLLOW`` and judged by ``fstat``, so the
    file that was checked is the file that is read: a path swapped for a symlink
    between the listing and the read opens nothing. A hardlink is not a symlink
    and cannot be refused from the path alone, so a file with more than one link
    is declined instead — ``AGENTS.md`` hardlinked to a key is that key's bytes.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return b""
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
            return b""
        return os.read(descriptor, max(max_bytes, 0) + 1)
    except OSError:
        return b""
    finally:
        os.close(descriptor)


def _is_pure_pointer(text: str) -> bool:
    """Whether *text* is nothing but `@path` references.

    A file whose whole content is `@AGENTS.md` is a pointer, not rules. Inlined,
    it would add a section header and a de-referenced path beside the target's
    own block, teaching the model nothing the listing does not already say — so
    the walk skips it, as long as skipping it costs no rules. See
    `_inline_instructions`.
    """
    body = text.strip()
    if not body:
        return False
    matches = get_path_references(body)
    if not matches:
        return False
    return not _without_references(body, matches).strip()


def _without_references(body: str, matches: list[re.Match]) -> str:
    """*body* with every reference cut out, so the prose around them can be judged."""
    kept: list[str] = []
    cursor = 0
    for match in matches:
        kept.append(body[cursor : match.start()])
        cursor = match.end()
    kept.append(body[cursor:])
    return "".join(kept)


def _reference_target(reference: str, directory: Path) -> Path | None:
    """The file *reference* names, read from *directory* or from the cwd.

    Both bases are tried: a sibling `@AGENTS.md` is what the file means, while
    `expand_prompt` resolves against the cwd. The first base that lands on an
    existing file wins; a reference that lands nowhere keeps the directory's
    answer, which no plan's inlined set can contain.
    """
    expanded = Path(os.path.expanduser(reference))
    candidates: list[Path] = []
    for base in (directory, Path.cwd()):
        try:
            candidates.append((base / expanded).resolve())
        except OSError:
            continue
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _leaf_targets(
    target: Path,
    next_hop: dict[Path, list[Path | None]],
    seen: frozenset[Path],
    depth: int = 0,
) -> tuple[set[Path], bool, bool]:
    """Every file *target* reaches, whether the chain circles back, and whether it was cut short.

    A pointer to a pointer has no content of its own, so what it finally names is
    what the prompt would have to carry. A cycle reaches nothing: it names no
    file and can never be a route to rules. A chain deeper than
    `MAX_POINTER_DEPTH` is *unresolved* rather than empty — the difference
    matters, because a pointer naming two files, one of them in the prompt and
    one at the end of a chain this walk did not follow, may not be skipped: the
    branch that was not followed is still a route to rules.
    """
    hops = next_hop.get(target)
    if hops is None:
        return {target}, False, False
    if target in seen:
        return set(), True, False
    if depth >= MAX_POINTER_DEPTH:
        return set(), False, True
    leaves: set[Path] = set()
    cyclic = False
    for hop in hops:
        if hop is None:
            # A reference that resolves nowhere: this pointer is the only route
            # to whatever it names, so it has to stay inlined.
            return {target}, False, False
        deeper, loop, unresolved = _leaf_targets(
            hop, next_hop, seen | {target}, depth + 1
        )
        if unresolved:
            return set(), cyclic, True
        leaves |= deeper
        cyclic = cyclic or loop
    return leaves, cyclic, False


def _inline_instructions(
    sources: list[Path], max_bytes: int
) -> tuple[list[str], set[Path], dict[Path, Path]]:
    """Inline instruction files until *max_bytes* is spent.

    Walks *sources* most specific first and stops at the first file that does not
    fit: a broader file is never inlined past a dropped narrower one, because
    that would hand the model parent-directory rules while withholding the rules
    for the directory it is editing. A budget too small to inline the nearest
    file therefore inlines nothing and lists everything.

    A file that is only a pointer (`CLAUDE.md` holding `@AGENTS.md`) is skipped
    when its target is in the prompt — what it names arrives in the target's own
    block, and its own bytes are all it contributes. A pointer whose target the
    budget drops is kept: it is then the only route to those rules. Unless
    skipping the pointer is what lets the target fit, which is why the plan is
    taken with *every* pointer skipped: thirteen bytes of `@../AGENTS.md` must
    not starve the 1,490-byte file it points at. A cycle names no file and can
    never be a route, so it is skipped too.

    The plan is the roomiest walk there is, so a pointer the plan kept can still
    cost its target when it comes back: every claim is checked against the final
    walk, and a pointer whose target fell out is inlined instead of described
    (`_walk_with_skips`).

    Returns the rendered blocks, the paths they cover, and the pointer files
    mapped to the file the prompt actually carries, not to the next hop.
    """
    texts = {path: _read_instruction_bytes(path, max_bytes) for path in sources}
    decoded = {path: text.decode("utf-8", "replace") for path, text in texts.items()}
    pointers = [path for path in sources if _is_pure_pointer(decoded[path])]
    next_hop = {
        path.resolve(): [
            _reference_target(match.group("path"), path.parent)
            for match in get_path_references(decoded[path])
        ]
        for path in pointers
    }
    _, without_pointers = _walk_instructions(
        sources, texts, max_bytes, skip=frozenset(pointers)
    )
    covered = {path.resolve() for path in without_pointers}
    skipped = _skip_pointers(pointers, next_hop, covered)
    blocks, inlined, skipped = _walk_with_skips(sources, texts, max_bytes, skipped)
    return blocks, inlined, _resolve_pointer_targets(skipped)


def _skip_pointers(
    pointers: list[Path],
    next_hop: dict[Path, list[Path | None]],
    covered: set[Path],
) -> dict[Path, Path]:
    """The pointers whose rules the prompt already carries, and the file each names.

    Skipping is only safe when every branch the walk followed ends in a file the
    prompt holds. A branch cut short by `MAX_POINTER_DEPTH` is still a route to
    rules, so its pointer is kept whole rather than skipped for the branches that
    did resolve. A cycle names no file and can never be a route, so it is skipped
    and reported against its first hop.
    """
    skipped: dict[Path, Path] = {}
    for path in pointers:
        hops = next_hop[path.resolve()]
        leaves, cyclic, unresolved = _leaf_targets(
            path.resolve(), next_hop, frozenset()
        )
        if unresolved:
            continue
        if leaves and leaves <= covered:
            skipped[path] = sorted(leaves)[0]
        elif cyclic and hops and hops[0] is not None:
            skipped[path] = hops[0]
    return skipped


def _walk_with_skips(
    sources: list[Path],
    texts: dict[Path, bytes],
    max_bytes: int,
    skipped: dict[Path, Path],
) -> tuple[list[str], set[Path], dict[Path, Path]]:
    """Render the blocks, dropping a skip the final budget did not honour.

    The skip set is decided against the roomiest walk there is — the one that
    drops *every* pointer. A pointer the plan kept can still cost its target
    once it comes back: a more specific pointer whose reference resolves nowhere
    spends the bytes the plan had counted on the target, and the target falls
    out. A pointer left under a "points at" note would then name rules the prompt
    does not carry, so the claim goes, the pointer's own line comes back, and the
    walk runs again. Each pass removes at least one claim, so it ends.

    A claim naming another skipped pointer is a cycle: it never reaches a file the
    prompt could hold, and the listing already drops its note
    (`_resolve_pointer_targets`).
    """
    while True:
        blocks, inlined = _walk_instructions(
            sources, texts, max_bytes, skip=frozenset(skipped)
        )
        honoured = {
            pointer: target
            for pointer, target in skipped.items()
            if target in skipped or target in inlined
        }
        if len(honoured) == len(skipped):
            return blocks, inlined, honoured
        skipped = honoured


def _resolve_pointer_targets(pointers: dict[Path, Path]) -> dict[Path, Path]:
    """Each pointer mapped to the file the prompt carries, following the chain.

    `CLAUDE.md -> @GEMINI.md -> @AGENTS.md` is two hops, and a listing that named
    the middle file would claim something is inlined when it is not. A chain
    that circles back has no terminal file, so the pointer keeps its skip — its
    content is a reference either way — but loses its note rather than naming a
    file the prompt does not hold. A chain longer than `MAX_POINTER_DEPTH` is not
    followed either: the walk that decided the skip already treats that length as
    broken, and this walk must not be the one place that trusts it.
    """
    next_hop = {path.resolve(): target for path, target in pointers.items()}
    terminal: dict[Path, Path] = {}
    for start, first in pointers.items():
        seen = {start.resolve()}
        target: Path | None = first
        for _ in range(MAX_POINTER_DEPTH):
            if target is None:
                break
            here = target.resolve()
            if here in seen:
                target = None
                break
            seen.add(here)
            hop = next_hop.get(here)
            if hop is None:
                break
            target = hop
        else:
            target = None
        if target is not None:
            terminal[start] = target
    return terminal


def _walk_instructions(
    sources: list[Path],
    texts: dict[Path, bytes],
    max_bytes: int,
    skip: frozenset[Path],
) -> tuple[list[str], set[Path]]:
    """Render the instruction blocks the byte budget admits, ignoring *skip*.

    Accounting is on the bytes read rather than on the decoded string: decoding
    and re-encoding can change the count — a replacement character costs three
    bytes where the cut multibyte tail cost one — and the budget is a promise
    about bytes.
    """
    blocks: list[str] = []
    inlined: set[Path] = set()
    remaining = max(max_bytes, 0)
    for path in sources:
        raw = texts.get(path, b"")
        if not raw.strip() or path in skip:
            continue
        note = ""
        if len(raw) <= remaining:
            body = raw.decode("utf-8", "replace")
            remaining -= len(raw)
        elif not inlined and remaining >= _MIN_INLINE_BYTES:
            # The most specific file is truncated rather than dropped: its rules
            # are the ones the next edit will violate.
            body = raw[:remaining].decode("utf-8", "ignore").rstrip()
            note = "\n[TRUNCATED — the file is longer than the prompt budget; read it for the rest.]"
            remaining = 0
        else:
            break
        blocks.append(
            f"#### Instructions from: `{path}`\n\n"
            f"{_neutralize_references(body)}{note}"
        )
        inlined.add(path)
    return blocks, inlined


def _neutralize_references(text: str) -> str:
    """*text* with every `@path` de-referenced, so prompt expansion cannot fetch it.

    Instruction content is rules to be read, not prompt syntax. `expand_prompt`
    runs over the composed prompt when the agent is built and resolves every
    `@path` it finds — with no byte budget and no project boundary. A rule file
    that mentions `@/home/user/.aws/credentials` would have that file read and
    appended to the prompt, and the user would never see it happen.

    The path itself is left in the text, so the model can still read it
    deliberately with `Read` when the rule actually applies.
    """
    matches = get_path_references(text)
    if not matches:
        return text
    parts: list[str] = []
    cursor = 0
    for match in matches:
        parts.append(text[cursor : match.start()])
        parts.append(f"`{match.group('path')}`")
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts)


def _listing_note(path: Path, inlined: set[Path], pointers: dict[Path, Path]) -> str:
    """How the file listing marks a doc whose content is already in the prompt.

    A pointer file is called what it is: its eleven bytes are `@AGENTS.md`, and
    a listing that just says "read this" invites a wasted read.
    """
    if path in inlined:
        return " — inlined above"
    target = pointers.get(path)
    if target is not None:
        return f" — a pointer to `{target}`, inlined above"
    return ""


def _is_user_level_dir(directory: Path) -> bool:
    """True for home itself or a home-level config directory.

    A home-level directory is one ``LLM_CONFIG_DIR_NAMES`` names under home —
    ``~/.claude``, ``~/.zrb`` — or an absolute config root such as the one
    ``$CLAUDE_CONFIG_DIR`` points at. ``False`` when home cannot be resolved.
    """
    names, roots = split_config_dir_patterns(CFG.LLM_CONFIG_DIR_NAMES)
    try:
        home = Path.home().resolve()
        resolved = directory.resolve()
        home_dirs = [(home / name).resolve() for name in names]
        absolute_roots = [root.resolve() for root in roots]
    except Exception:
        return False
    return resolved == home or resolved in home_dirs or resolved in absolute_roots


def get_search_directories() -> list[Path]:
    try:
        home_str = str(Path.home())
    except Exception:
        home_str = ""
    try:
        cwd_str = str(Path.cwd())
    except Exception:
        cwd_str = ""
    names, roots = split_config_dir_patterns(CFG.LLM_CONFIG_DIR_NAMES)
    return [
        Path(p)
        for p in _get_search_directories_cached(
            home_str, cwd_str, tuple(names), tuple(str(root) for root in roots)
        )
    ]


@lru_cache(maxsize=8)
def _get_search_directories_cached(
    home_str: str, cwd_str: str, names: tuple[str, ...], roots: tuple[str, ...]
) -> tuple[str, ...]:
    """Compute the project-doc search path once per (home, cwd, config) tuple."""
    dirs: list[str] = []
    if home_str:
        home = Path(home_str)
        dirs.extend(str(home / name) for name in names)
    dirs.extend(roots)
    if cwd_str:
        cwd = Path(cwd_str)
        # Root first, so configs closer to cwd override general ones.
        for parent in reversed(list(cwd.parents)):
            dirs.append(str(parent))
        dirs.append(str(cwd))
    return tuple(dirs)
