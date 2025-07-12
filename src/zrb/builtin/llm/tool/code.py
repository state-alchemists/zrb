import json
import os

from zrb.builtin.llm.tool.file import DEFAULT_EXCLUDED_PATTERNS, is_excluded
from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext

_DEFAULT_EXTENSIONS = [
    "py",
    "go",
    "java",
    "ts",
    "js",
    "rs",
    "rb",
    "php",
    "sh",
    "bash",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "swift",
    "kt",
    "scala",
    "m",
    "pl",
    "lua",
    "sql",
    "html",
    "css",
    "scss",
    "less",
    "json",
    "yaml",
    "yml",
    "toml",
    "ini",
    "xml",
    "md",
    "rst",
    "txt",
]


async def analyze_repo(
    ctx: AnyContext,
    path: str,
    goal: str,
    extensions: list[str] = _DEFAULT_EXTENSIONS,
    exclude_patterns: list[str] = DEFAULT_EXCLUDED_PATTERNS,
    extraction_token_threshold: int | None = None,
    summarization_token_threshold: int | None = None,
) -> str:
    """
    Performs a deep, goal-oriented analysis of a code repository or directory.

    This powerful tool recursively reads all relevant files in a directory, extracts key information, and then summarizes that information in relation to a specific goal. It uses intelligent sub-agents for extraction and summarization, making it ideal for complex tasks that require a holistic understanding of a codebase.

    Use this tool for:
    - Understanding a large or unfamiliar codebase.
    - Generating high-level summaries of a project's architecture.
    - Performing a preliminary code review.
    - Creating documentation or diagrams (e.g., "Generate a Mermaid C4 diagram for this service").
    - Answering broad questions like "How does the authentication in this project work?".

    Args:
        path (str): The path to the directory or repository to analyze.
        goal (str): A clear and specific description of what you want to achieve. A good goal is critical for getting a useful result. For example: "Understand the database schema by analyzing all the .sql files" or "Create a summary of all the API endpoints defined in the 'api' directory".
        extensions (list[str], optional): A list of file extensions to include in the analysis. Defaults to a comprehensive list of common code and configuration files.
        exclude_patterns (list[str], optional): A list of glob patterns for files and directories to exclude from the analysis. Defaults to common patterns like '.git', 'node_modules', and '.venv'.
        extraction_token_threshold (int, optional): The maximum token threshold for the extraction sub-agent.
        summarization_token_threshold (int, optional): The maximum token threshold for the summarization sub-agent.

    Returns:
        str: A detailed, markdown-formatted analysis and summary of the repository, tailored to the specified goal.
    Raises:
        Exception: If an error occurs during the analysis.
    """
    if extraction_token_threshold is None:
        extraction_token_threshold = CFG.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
    if summarization_token_threshold is None:
        summarization_token_threshold = (
            CFG.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
        )
    abs_path = os.path.abspath(os.path.expanduser(path))
    file_metadatas = _get_file_metadatas(abs_path, extensions, exclude_patterns)
    ctx.print("Extraction")
    extracted_infos = await _extract_info(
        ctx,
        file_metadatas=file_metadatas,
        goal=goal,
        token_limit=extraction_token_threshold,
    )
    if len(extracted_infos) == 1:
        return extracted_infos[0]
    ctx.print("Summarization")
    summarized_infos = extracted_infos
    while len(summarized_infos) > 1:
        ctx.print("Summarization")
        summarized_infos = await _summarize_info(
            ctx,
            extracted_infos=summarized_infos,
            goal=goal,
            token_limit=summarization_token_threshold,
        )
    return summarized_infos[0]


def _get_file_metadatas(
    dir_path: str,
    extensions: list[str],
    exclude_patterns: list[str],
) -> list[dict[str, str]]:
    metadata_list = []
    for root, _, files in os.walk(dir_path):
        files.sort()
        for file in files:
            if not any(file.endswith(f".{ext}") for ext in extensions):
                continue
            file_path = os.path.join(root, file)
            if is_excluded(file_path, exclude_patterns):
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    rel_path = os.path.relpath(file_path, dir_path)
                    metadata_list.append({"path": rel_path, "content": f.read()})
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
    metadata_list.sort(key=lambda m: m["path"])
    return metadata_list


async def _extract_info(
    ctx: AnyContext,
    file_metadatas: list[dict[str, str]],
    goal: str,
    token_limit: int,
) -> list[str]:
    extract = create_sub_agent_tool(
        tool_name="extract",
        tool_description="extract",
        system_prompt=CFG.LLM_REPO_EXTRACTOR_SYSTEM_PROMPT,
    )
    extracted_infos = []
    content_buffer = []
    current_token_count = 0
    for metadata in file_metadatas:
        path = metadata.get("path", "")
        content = metadata.get("content", "")
        file_obj = {"path": path, "content": content}
        file_str = json.dumps(file_obj)
        if current_token_count + llm_rate_limitter.count_token(file_str) > token_limit:
            if content_buffer:
                prompt = _create_extract_info_prompt(goal, content_buffer)
                extracted_info = await extract(
                    ctx, llm_rate_limitter.clip_prompt(prompt, token_limit)
                )
                extracted_infos.append(extracted_info)
            content_buffer = [file_obj]
            current_token_count = llm_rate_limitter.count_token(file_str)
        else:
            content_buffer.append(file_obj)
            current_token_count += llm_rate_limitter.count_token(file_str)

    # Process any remaining content in the buffer
    if content_buffer:
        prompt = _create_extract_info_prompt(goal, content_buffer)
        extracted_info = await extract(
            ctx, llm_rate_limitter.clip_prompt(prompt, token_limit)
        )
        extracted_infos.append(extracted_info)
    return extracted_infos


def _create_extract_info_prompt(goal: str, content_buffer: list[dict]) -> str:
    return json.dumps(
        {
            "main_assistant_goal": goal,
            "files": content_buffer,
        }
    )


async def _summarize_info(
    ctx: AnyContext,
    extracted_infos: list[str],
    goal: str,
    token_limit: int,
) -> list[str]:
    summarize = create_sub_agent_tool(
        tool_name="extract",
        tool_description="extract",
        system_prompt=CFG.LLM_REPO_SUMMARIZER_SYSTEM_PROMPT,
    )
    summarized_infos = []
    content_buffer = ""
    for extracted_info in extracted_infos:
        new_prompt = content_buffer + extracted_info
        if llm_rate_limitter.count_token(new_prompt) > token_limit:
            if content_buffer:
                prompt = _create_summarize_info_prompt(goal, content_buffer)
                summarized_info = await summarize(
                    ctx, llm_rate_limitter.clip_prompt(prompt, token_limit)
                )
                summarized_infos.append(summarized_info)
            content_buffer = extracted_info
        else:
            content_buffer += extracted_info + "\n"

    # Process any remaining content in the buffer
    if content_buffer:
        prompt = _create_summarize_info_prompt(goal, content_buffer)
        summarized_info = await summarize(
            ctx, llm_rate_limitter.clip_prompt(prompt, token_limit)
        )
        summarized_infos.append(summarized_info)
    return summarized_infos


def _create_summarize_info_prompt(goal: str, content_buffer: str) -> str:
    return json.dumps(
        {
            "main_assistant_goal": goal,
            "extracted_info": content_buffer,
        }
    )
