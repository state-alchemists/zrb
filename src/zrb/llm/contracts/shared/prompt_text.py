"""Prompt text by name: the override chain, the placeholders, the bundled files.

This is the half of prompting that is pure lookup — it reads a section and
fills its placeholders, and knows nothing about how sections are composed. It
lives at L0 because a tool that builds its own small agent needs a system
prompt, and `tool/` may not import `prompt/`: the two would then import each
other (ADR-0049). The bundled section files are beside it, in `markdown/`.
"""

import os
import re
from functools import lru_cache
from pathlib import Path

from zrb.config.config import CFG
from zrb.util.dir_search import get_dirs_up_to_home
from zrb.util.string.conversion import to_snake_case


def get_prompt(name: str, profile: str | None = None, **extra_replacements: str) -> str:
    """Load a prompt by name and apply all placeholder replacements.

        prompt = get_prompt("persona", profile="minimal", ASSISTANT_NAME="Zrb")

    The ``{CFG_<KEY>}`` a prompt names are filled from `CFG` when they hold a
    number or a switch; see `_fill_cfg_placeholders` for why a string setting is
    not. A name that is not filled is left as written, so a typo stays visible.

    Args:
        name: Prompt file name (without ``.md`` suffix), e.g. ``"persona"``,
            ``"workflow"``, ``"examples"``.
        profile: Optional explicit profile adjustment. When supplied,
            ``{name}.{profile}`` is resolved through the normal override chain.
        extra_replacements: Additional ``{PLACEHOLDER}`` → value entries
            merged on top of the standard replacements.

    Returns:
        The rendered prompt string with all placeholders replaced.
    """
    prompt = _load_prompt_for_profile(name, profile)
    prompt = _replace_prompt_placeholders(prompt, _cfg_string_replacements())
    replacements = {
        # Allow callers to pass either "ASSISTANT_NAME" or "{ASSISTANT_NAME}"
        key if key.startswith("{") and key.endswith("}") else f"{{{key}}}": value
        for key, value in extra_replacements.items()
    }
    prompt = _replace_prompt_placeholders(prompt, replacements)
    return _fill_cfg_placeholders(prompt)


def _load_prompt_for_profile(name: str, profile: str | None) -> str:
    """Resolve a section's raw text, preferring a named profile file."""
    if profile:
        variant = get_default_prompt(f"{name}.{profile}")
        if variant:
            return variant
    return get_default_prompt(name)


def get_default_prompt(name: str) -> str:
    """The raw text of prompt *name*, from the first of these that has it:

    1. a ``{LLM_PROMPT_DIR}/{name}.md`` override in the project or home search path;
    2. the ``{ENV_PREFIX}_LLM_PROMPT_{NAME}`` environment variable;
    3. ``{LLM_BASE_PROMPT_DIR}/{name}.md``;
    4. the file bundled beside this module, in ``markdown/``.
    """
    cwd = os.getcwd()
    prompt_dir = CFG.LLM_PROMPT_DIR

    custom = _find_custom_prompt(name, cwd, prompt_dir)
    if custom:
        return custom

    env_prefix = CFG.ENV_PREFIX
    env_value = os.getenv(f"{env_prefix}_LLM_PROMPT_{to_snake_case(name).upper()}", "")
    if env_value:
        return env_value

    base_prompt_dir = CFG.LLM_BASE_PROMPT_DIR
    if base_prompt_dir:
        base = _read_prompt_file(
            os.path.abspath(os.path.join(base_prompt_dir, f"{name}.md"))
        )
        if base is not None:
            return base

    return _read_package_prompt(name)


def _find_custom_prompt(name: str, cwd: str, prompt_dir: str) -> str:
    """Return the first matching local override content, or empty string.

    Not cached: local overrides may be edited mid-session.
    """
    for search_path in _get_default_prompt_search_path(cwd):
        local = _read_prompt_file(
            os.path.abspath(os.path.join(search_path, prompt_dir, f"{name}.md"))
        )
        if local is not None:
            return local
    return ""


def _read_prompt_file(path: str) -> str | None:
    """The text of the prompt file at *path*; ``None`` when it is missing or
    unreadable."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        CFG.LOGGER.debug(f"Failed to read prompt {path}: {e}")
        return None


def _get_default_prompt_search_path(cwd: str) -> tuple[str, ...]:
    return _get_default_prompt_search_path_cached(
        cwd, CFG.LLM_SEARCH_PROJECT_ENABLED, CFG.LLM_SEARCH_HOME_ENABLED
    )


@lru_cache(maxsize=32)
def _get_default_prompt_search_path_cached(
    cwd: str, search_project: bool, search_home: bool
) -> tuple[str, ...]:
    """Directories to check for a ``{prompt_dir}/{name}.md`` override, in order.

    Honors ``LLM_SEARCH_PROJECT_ENABLED`` (cwd ancestors up to home) and
    ``LLM_SEARCH_HOME_ENABLED``, as skill and agent discovery do.
    """
    home_path = os.path.abspath(os.path.expanduser("~"))
    search_paths = get_dirs_up_to_home(cwd, home_path) if search_project else []
    if search_home and home_path not in search_paths:
        search_paths.append(home_path)
    return tuple(search_paths)


@lru_cache(maxsize=32)
def _read_package_prompt(name: str) -> str:
    """Read a bundled prompt .md file (cached; bundled files never change)."""
    file_path = Path(__file__).parent / "markdown" / f"{name}.md"
    if not file_path.is_file():
        return ""
    with open(file_path, encoding="utf-8") as f:
        return f.read()


#: A placeholder naming a setting: `{CFG_LLM_MEMORY_DIARY_MAX_CHARS}`.
_CFG_PLACEHOLDER = re.compile(r"\{CFG_([A-Z][A-Z0-9_]*)\}")

#: The string settings a prompt may name, one by one.
#:
#: A prompt is sent to a model provider and kept in the history, so a string in
#: it is a disclosure waiting to happen. These three were nameable before this
#: module resolved anything by itself and are names and prefixes, not secrets;
#: everything else that is a string — a key, a token, a path holding a user's
#: name — must not be reachable from a repository's prompt override.
_PROMPT_STRING_SETTINGS = ("ROOT_GROUP_NAME", "LLM_ASSISTANT_NAME", "ENV_PREFIX")


def _cfg_string_replacements() -> dict[str, str]:
    """The values of the string settings a prompt may name, keyed by placeholder."""
    replacements: dict[str, str] = {}
    for attr in _PROMPT_STRING_SETTINGS:
        value = getattr(CFG, attr, None)
        if value is not None:
            replacements[f"{{CFG_{attr}}}"] = str(value)
    return replacements


def _fill_cfg_placeholders(prompt: str) -> str:
    """Fill every ``{CFG_<KEY>}`` this prompt names when it holds a number.

    Only numbers and switches. What goes stale in a prompt is a limit — a page
    length, a timeout, a count — and that is worth naming instead of copying. A
    credential is a string, and this text is sent to the model, so the type is
    the rule: `isinstance(value, (int, float, bool))` and nothing else, because
    a timeout is a float as often as a count is an int. A string setting is left
    as written rather than guessed at, and the few strings a prompt has always
    been able to name are listed in `_PROMPT_STRING_SETTINGS`.

    Nothing is cached. The work is proportional to the placeholders the prompt
    actually carries, and the value should be the one the setting holds when the
    prompt is rendered.
    """

    def resolve(match: re.Match[str]) -> str:
        value = getattr(CFG, match.group(1), None)
        numeric = isinstance(value, (int, float, bool))
        return str(value) if numeric else match.group(0)

    return _CFG_PLACEHOLDER.sub(resolve, prompt)


def _replace_prompt_placeholders(prompt: str, replacements: dict[str, str]) -> str:
    """Replace all placeholders in a prompt string."""
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt
