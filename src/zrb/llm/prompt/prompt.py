import os
from functools import lru_cache
from pathlib import Path

from zrb.config.config import CFG
from zrb.util.string.conversion import to_snake_case


def get_persona_prompt(assistant_name: str | None = None) -> str:
    effective_assistant_name = (
        assistant_name if assistant_name else CFG.LLM_ASSISTANT_NAME
    )
    prompt = get_default_prompt("persona")
    replacements = _get_prompt_replacements()
    replacements["{ASSISTANT_NAME}"] = effective_assistant_name
    return _replace_prompt_placeholders(prompt, replacements)


def get_mandate_prompt() -> str:
    prompt = get_default_prompt("mandate")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_git_mandate_prompt() -> str:
    prompt = get_default_prompt("git_mandate")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_summarizer_system_prompt() -> str:
    return get_conversational_summarizer_system_prompt()


def get_conversational_summarizer_system_prompt() -> str:
    prompt = get_default_prompt("conversational_summarizer")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_message_summarizer_system_prompt() -> str:
    prompt = get_default_prompt("message_summarizer")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_file_extractor_system_prompt() -> str:
    prompt = get_default_prompt("file_extractor")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_repo_extractor_system_prompt() -> str:
    prompt = get_default_prompt("repo_extractor")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_repo_summarizer_system_prompt() -> str:
    prompt = get_default_prompt("repo_summarizer")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_web_summarizer_system_prompt() -> str:
    prompt = get_default_prompt("web_summarizer")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_journal_prompt() -> str:
    prompt = get_default_prompt("journal_mandate")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_journal_reminder_prompt() -> str:
    prompt = get_default_prompt("journal_reminder")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_multimodal_image_prompt() -> str:
    prompt = get_default_prompt("multimodal_image")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


def get_multimodal_audio_prompt() -> str:
    prompt = get_default_prompt("multimodal_audio")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


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
            except Exception:
                pass

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
            except Exception:
                pass
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
    """Return replacement dict, re-computed only when the journal index changes."""
    journal_index_file = os.path.abspath(
        os.path.expanduser(
            os.path.join(CFG.LLM_JOURNAL_DIR, CFG.LLM_JOURNAL_INDEX_FILE),
        )
    )
    try:
        mtime = os.path.getmtime(journal_index_file)
    except OSError:
        mtime = 0.0
    return dict(_get_prompt_replacements_cached(mtime))


@lru_cache(maxsize=4)
def _get_prompt_replacements_cached(journal_mtime: float) -> dict[str, str]:
    """Compute all prompt replacements; keyed by journal index mtime so it
    refreshes automatically whenever the user updates their journal."""
    replacements: dict[str, str] = {}
    cfg_attributes = [
        "LLM_JOURNAL_DIR",
        "LLM_JOURNAL_INDEX_FILE",
        "ROOT_GROUP_NAME",
        "LLM_ASSISTANT_NAME",
        "ENV_PREFIX",
    ]
    for attr in cfg_attributes:
        if hasattr(CFG, attr):
            value = getattr(CFG, attr)
            if value is not None:
                placeholder = f"{{CFG_{attr}}}"
                replacements[placeholder] = str(value)

    journal_dir = os.path.abspath(os.path.expanduser(CFG.LLM_JOURNAL_DIR))
    journal_index_file = os.path.abspath(
        os.path.expanduser(
            os.path.join(CFG.LLM_JOURNAL_DIR, CFG.LLM_JOURNAL_INDEX_FILE),
        )
    )
    replacements["{CFG_LLM_JOURNAL_DIR_STATUS}"] = (
        "exists" if os.path.exists(journal_dir) else "inexist"
    )
    replacements["{CFG_LLM_JOURNAL_INDEX_FILE_STATUS}"] = (
        "exists" if os.path.isfile(journal_index_file) else "inexist"
    )
    replacements["{JOURNAL_INDEX_CONTENT}"] = "<Empty>"
    if os.path.isfile(journal_index_file):
        with open(journal_index_file, encoding="utf-8") as f:
            content = f.read()
            if len(content) > 1000:
                content = content[:1000] + " (...more)"
            replacements["{JOURNAL_INDEX_CONTENT}"] = content
    return replacements


def _replace_prompt_placeholders(prompt: str, replacements: dict[str, str]) -> str:
    """Replace all placeholders in a prompt string."""
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt
