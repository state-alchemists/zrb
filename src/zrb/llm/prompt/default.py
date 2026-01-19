from zrb.config.config import CFG
import os


def get_default_prompt(name: str) -> str:
    cwd = os.path.dirname(__file__)
    with open(os.path.join(cwd, "markdown", f"{name}.md")) as f:
        return f.read()


def get_assistant_system_prompt(assistant_name: str | None = None) -> str:
    effective_assistant_name = assistant_name if assistant_name else CFG.ROOT_GROUP_NAME
    prompt = get_default_prompt("assistant")
    return prompt.replace("{ASSISTANT_NAME}", effective_assistant_name)


def get_summarizer_system_prompt() -> str:
    return get_default_prompt("summarizer")


def get_file_extractor_system_prompt() -> str:
    return get_default_prompt("file_extractor")


def get_repo_extractor_system_prompt() -> str:
    return get_default_prompt("repo_extractor")


def get_repo_summarizer_system_prompt() -> str:
    return get_default_prompt("repo_summarizer")
