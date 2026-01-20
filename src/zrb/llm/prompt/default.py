import os

from zrb.config.config import CFG
from zrb.util.string.conversion import to_snake_case


def get_default_prompt(name: str) -> str:
    # 1. Check for local project override (configured via LLM_PROMPT_DIR)
    prompt_dir = getattr(CFG, "LLM_PROMPT_DIR", ".zrb/llm/prompt")
    local_prompt_path = os.path.abspath(
        os.path.join(os.getcwd(), prompt_dir, f"{name}.md")
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
    with open(os.path.join(cwd, "markdown", f"{name}.md"), "r", encoding="utf-8") as f:
        return f.read()


def get_persona_prompt(assistant_name: str | None = None) -> str:
    effective_assistant_name = (
        assistant_name if assistant_name else CFG.LLM_ASSISTANT_NAME
    )
    prompt = get_default_prompt("persona")
    return prompt.replace("{ASSISTANT_NAME}", effective_assistant_name)


def get_mandate_prompt() -> str:
    return get_default_prompt("mandate")


def get_summarizer_system_prompt() -> str:
    return get_default_prompt("summarizer")


def get_file_extractor_system_prompt() -> str:
    return get_default_prompt("file_extractor")


def get_repo_extractor_system_prompt() -> str:
    return get_default_prompt("repo_extractor")


def get_repo_summarizer_system_prompt() -> str:
    return get_default_prompt("repo_summarizer")
