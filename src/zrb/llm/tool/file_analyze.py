import os
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.tool.file_read import read_file
from zrb.llm.tool.file_search import search_files


async def analyze_file(
    path: Annotated[str, Field(description="File to analyze.")],
    query: Annotated[
        str, Field(description="What to find or answer about the file's content.")
    ],
) -> str:
    """
    Deep semantic analysis of a file via LLM sub-agent. Slow and resource-intensive.
    """
    # lazy: transitively heavy via internal — zrb.llm.agent loads pydantic_ai
    from zrb.llm.agent import create_agent, run_agent
    from zrb.llm.config.limiter import get_run_llm_limiter
    from zrb.llm.config.model_resolver import resolve_configured_model
    from zrb.llm.prompt.prompt import get_prompt

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return (
            f"Error: File not found: {path}. "
            "[SYSTEM SUGGESTION]: Check the path; use List to see what exists "
            "nearby."
        )

    content = read_file(abs_path)
    if content.startswith("Error:"):
        return content

    token_threshold = CFG.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
    char_limit = token_threshold * 4

    clipped_content = _clip_numbered(content, char_limit)

    system_prompt = get_prompt("file_extractor")

    agent = create_agent(
        model=resolve_configured_model(),
        system_prompt=system_prompt,
        tools=[
            read_file,
            search_files,
        ],
        resolve_model=False,
    )

    user_message = f"""
    Instruction: {query}
    File Path: {abs_path}
    File Content:
    ```
    {clipped_content}
    ```
    """

    result, _ = await run_agent(
        agent=agent,
        message=user_message,
        message_history=[],
        limiter=get_run_llm_limiter(),
    )

    return str(result)


def _clip_numbered(text: str, max_chars: int) -> str:
    """Clip ``Read``'s output to ``max_chars`` of file content.

    The ``cat -n`` prefix is not counted against the budget; a line with no
    tab counts at full length.
    """
    kept: list[str] = []
    total = 0
    for line in text.splitlines(keepends=True):
        _, tab, payload = line.partition("\t")
        total += len(payload) if tab else len(line)
        if total > max_chars and kept:
            kept.append("\n...[TRUNCATED]")
            break
        kept.append(line)
    return "".join(kept)
