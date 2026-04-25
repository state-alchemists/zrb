import os

from zrb.config.config import CFG
from zrb.util.truncate import truncate_output

from zrb.llm.tool.file_read import read_file
from zrb.llm.tool.file_search import search_files


async def analyze_file(path: str, query: str, auto_truncate: bool = True) -> str:
    """
    Deep semantic analysis of a file via LLM sub-agent. Slow and resource-intensive.
    """
    from zrb.llm.agent import create_agent, run_agent
    from zrb.llm.config.config import llm_config
    from zrb.llm.config.limiter import llm_limiter
    from zrb.llm.prompt.prompt import get_file_extractor_system_prompt

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: File not found: {path}"

    content = read_file(abs_path, auto_truncate=auto_truncate)
    if content.startswith("Error:"):
        return content

    token_threshold = CFG.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
    char_limit = token_threshold * 4

    clipped_content, _ = truncate_output(
        content,
        head_lines=CFG.LLM_FILE_READ_LINES,
        tail_lines=CFG.LLM_FILE_READ_LINES,
        max_chars=char_limit,
    )

    system_prompt = get_file_extractor_system_prompt()

    agent = create_agent(
        model=llm_config.resolve_model(),
        system_prompt=system_prompt,
        tools=[
            read_file,
            search_files,
        ],
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
        limiter=llm_limiter,
    )

    return str(result)
