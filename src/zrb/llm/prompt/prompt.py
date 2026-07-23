import os
from functools import lru_cache
from pathlib import Path

from zrb.config.config import CFG
from zrb.llm.prompt.profile import BASE_PROFILE
from zrb.util.string.conversion import to_snake_case


def get_prompt(name: str, profile: str | None = None, **extra_replacements: str) -> str:
    """Load a prompt by name and apply all placeholder replacements.

    This is the canonical function that replaces all individual
    ``get_*_prompt()`` functions. Call it directly:

        prompt = get_prompt("mandate")
        prompt = get_prompt("persona", ASSISTANT_NAME="Zrb")
        prompt = get_prompt("persona", profile="explicit")

    Standard replacements (journal dir, root group name, etc.) are
    always applied automatically.  Pass extra keyword arguments for
    prompt-specific placeholders such as ``ASSISTANT_NAME``.

    Args:
        name: Prompt file name (without ``.md`` suffix), e.g. ``"persona"``,
            ``"mandate"``, ``"journal_mandate"``.
        profile: Optional profile variant (ADR-0083). When set to a non-base
            profile, ``{name}.{profile}`` is resolved first through the full
            override chain, falling back to the base ``{name}`` when no variant
            exists.
        extra_replacements: Additional ``{PLACEHOLDER}`` → value entries
            merged on top of the standard replacements.

    Returns:
        The rendered prompt string with all placeholders replaced.
    """
    prompt = _load_prompt_for_profile(name, profile)
    replacements = _get_prompt_replacements()
    for key, value in extra_replacements.items():
        # Allow callers to pass either "ASSISTANT_NAME" or "{ASSISTANT_NAME}"
        placeholder = key if key.startswith("{") and key.endswith("}") else f"{{{key}}}"
        replacements[placeholder] = value
    return _replace_prompt_placeholders(prompt, replacements)


def _load_prompt_for_profile(name: str, profile: str | None) -> str:
    """Resolve a section's raw text, preferring a profile-specific variant.

    Tries ``{name}.{profile}`` through the full override chain first (so a
    project override of the variant still wins over the packaged base), falling
    back to the base ``{name}`` when no variant resolves. The base ``*.md`` files
    are the ``terse`` profile, so ``terse``/``None``/empty short-circuit straight
    to the base. See ADR-0083.
    """
    if profile and profile != BASE_PROFILE:
        variant = get_default_prompt(f"{name}.{profile}")
        if variant:
            return variant
    return get_default_prompt(name)


# ── Prompt loading ──────────────────────────────────────────────────────


def get_default_prompt(name: str) -> str:
    cwd = os.getcwd()
    prompt_dir = CFG.LLM_PROMPT_DIR

    # 1. Check for local project override (configured via LLM_PROMPT_DIR)
    custom = _find_custom_prompt(name, cwd, prompt_dir)
    if custom:
        return custom

    # 2. Load from environment
    env_prefix = CFG.ENV_PREFIX
    env_value = os.getenv(f"{env_prefix}_LLM_PROMPT_{to_snake_case(name).upper()}", "")
    if env_value:
        return env_value

    # 3. Check for base prompt directory (configured via LLM_BASE_PROMPT_DIR)
    base_prompt_dir = CFG.LLM_BASE_PROMPT_DIR
    if base_prompt_dir:
        base_prompt_path = os.path.abspath(os.path.join(base_prompt_dir, f"{name}.md"))
        if os.path.exists(base_prompt_path):
            try:
                with open(base_prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                CFG.LOGGER.debug(f"Failed to read prompt {base_prompt_path}: {e}")

    # 4. Fallback to package default (cached — bundled files never change at runtime)
    return _read_package_prompt(name)


@lru_cache(maxsize=64)
def _find_custom_prompt(name: str, cwd: str, prompt_dir: str) -> str:
    """Return the first matching local override content, or empty string."""
    for search_path in _get_default_prompt_search_path(cwd):
        local_prompt_path = os.path.abspath(
            os.path.join(search_path, prompt_dir, f"{name}.md")
        )
        if os.path.exists(local_prompt_path):
            try:
                with open(local_prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                CFG.LOGGER.debug(f"Failed to read prompt {local_prompt_path}: {e}")
    return ""


@lru_cache(maxsize=32)
def _get_default_prompt_search_path(cwd: str) -> tuple[str, ...]:
    home_path = os.path.abspath(os.path.expanduser("~"))
    search_paths = [cwd]
    try:
        if os.path.commonpath([cwd, home_path]) == home_path:
            temp_path = cwd
            while temp_path != home_path:
                new_temp_path = os.path.dirname(temp_path)
                if new_temp_path == temp_path:
                    break
                temp_path = new_temp_path
                search_paths.append(temp_path)
    except ValueError:
        pass
    return tuple(search_paths)


@lru_cache(maxsize=32)
def _read_package_prompt(name: str) -> str:
    """Read a bundled prompt .md file. Cached forever — these never change at runtime."""
    file_path = Path(__file__).parent / "markdown" / f"{name}.md"
    if not file_path.is_file():
        return ""
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def _get_prompt_replacements() -> dict[str, str]:
    """Return replacement dict, re-computed only when an input changes."""
    return dict(
        _get_prompt_replacements_cached(
            CFG.LLM_JOURNAL_DIR,
            CFG.LLM_JOURNAL_INDEX_FILE,
            CFG.ROOT_GROUP_NAME,
            CFG.LLM_ASSISTANT_NAME,
            CFG.ENV_PREFIX,
        )
    )


@lru_cache(maxsize=8)
def _get_prompt_replacements_cached(
    journal_dir: str,
    journal_index_name: str,
    root_group_name: str,
    assistant_name: str,
    env_prefix: str,
) -> dict[str, str]:
    """Compute config-derived prompt replacements; cached on every input.

    The journal index *content* is deliberately NOT included here. Embedding the
    mutable index in this cached system-prompt section invalidated the cacheable
    prefix every time the agent journaled mid-session; the snapshot is now
    injected into the ``<live-context>`` block instead (see ``live_context.py``
    and ADR-0082)."""
    replacements: dict[str, str] = {}
    cfg_values = {
        "LLM_JOURNAL_DIR": journal_dir,
        "LLM_JOURNAL_INDEX_FILE": journal_index_name,
        "ROOT_GROUP_NAME": root_group_name,
        "LLM_ASSISTANT_NAME": assistant_name,
        "ENV_PREFIX": env_prefix,
    }
    for attr, value in cfg_values.items():
        if value is not None:
            replacements[f"{{CFG_{attr}}}"] = str(value)
    return replacements


def _replace_prompt_placeholders(prompt: str, replacements: dict[str, str]) -> str:
    """Replace all placeholders in a prompt string."""
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt
