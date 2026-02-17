import os
from typing import Dict

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
    prompt = get_default_prompt("summarizer")
    replacements = _get_prompt_replacements()
    return _replace_prompt_placeholders(prompt, replacements)


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


def get_default_prompt(name: str) -> str:
    # 1. Check for local project override (configured via LLM_PROMPT_DIR)
    prompt_dir = getattr(CFG, "LLM_PROMPT_DIR", ".zrb/llm/prompt")
    for search_path in _get_default_prompt_search_path():
        local_prompt_path = os.path.abspath(
            os.path.join(search_path, prompt_dir, f"{name}.md")
        )
        if os.path.exists(local_prompt_path):
            try:
                with open(local_prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

    # 2. Load from environment
    env_prefix = CFG.ENV_PREFIX
    env_value = os.getenv(f"{env_prefix}_LLM_PROMPT_{to_snake_case(name).upper()}", "")
    if env_value:
        return env_value

    # 3. Fallback to package default
    cwd = os.path.dirname(__file__)
    file_path = os.path.join(cwd, "markdown", f"{name}.md")
    if not os.path.isfile(file_path):
        return ""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _get_default_prompt_search_path() -> list[str]:
    current_path = os.path.abspath(os.getcwd())
    home_path = os.path.abspath(os.path.expanduser("~"))
    search_paths = [current_path]
    try:
        if os.path.commonpath([current_path, home_path]) == home_path:
            temp_path = current_path
            while temp_path != home_path:
                new_temp_path = os.path.dirname(temp_path)
                if new_temp_path == temp_path:
                    break
                temp_path = new_temp_path
                search_paths.append(temp_path)
    except ValueError:
        pass
    return search_paths


def _get_prompt_replacements() -> Dict[str, str]:
    """Get all configuration values that should be replaced in prompts."""
    replacements = {}
    # Add CFG values with {CFG_*} pattern
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
    return replacements


def _replace_prompt_placeholders(prompt: str, replacements: Dict[str, str]) -> str:
    """Replace all placeholders in a prompt string."""
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt
