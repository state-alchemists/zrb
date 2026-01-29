import os
from typing import Literal

from zrb.config.config import CFG
from zrb.util.string.conversion import to_snake_case

SupportedRole = Literal["executor", "orchestrator", "planner", "researcher", "reviewer"]


def get_persona_prompt(
    assistant_name: str | None = None, role: str | SupportedRole | None = None
) -> str:
    effective_assistant_name = (
        assistant_name if assistant_name else CFG.LLM_ASSISTANT_NAME
    )
    prompt = get_default_prompt_by_role("persona", role)
    return prompt.replace("{ASSISTANT_NAME}", effective_assistant_name)


def get_mandate_prompt(role: str | SupportedRole | None = None) -> str:
    return get_default_prompt_by_role("mandate", role)


def get_summarizer_system_prompt() -> str:
    return get_default_prompt("summarizer")


def get_file_extractor_system_prompt() -> str:
    return get_default_prompt("file_extractor")


def get_repo_extractor_system_prompt() -> str:
    return get_default_prompt("repo_extractor")


def get_repo_summarizer_system_prompt() -> str:
    return get_default_prompt("repo_summarizer")


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


def get_default_prompt_by_role(
    name: str, role: str | SupportedRole | None = None
) -> str:
    prompt = get_default_prompt(f"{role}-{name}")
    if prompt.strip() != "":
        return prompt
    return get_default_prompt(name)
