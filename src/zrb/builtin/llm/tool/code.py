import json
import os

from zrb.builtin.llm.tool.file import DEFAULT_EXCLUDED_PATTERNS, is_excluded
from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.util.cli.style import stylize_faint

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
    query: str,
    extensions: list[str] = _DEFAULT_EXTENSIONS,
    exclude_patterns: list[str] = DEFAULT_EXCLUDED_PATTERNS,
    extraction_token_threshold: int | None = None,
    summarization_token_threshold: int | None = None,
) -> str:
    """
    Analyzes a code repository or directory to answer a specific query.

    CRITICAL: The query must contain ALL necessary context, instructions, and information.
        The sub-agent performing the analysis does NOT share your current conversation
        history, memory, or global context.
        The quality of analysis depends entirely on the query. Vague queries yield poor
        results.

    IMPORTANT: This tool can be slow and expensive on large repositories. Use judiciously.

    Example:
    analyze_repo(
        path='src/my_project',
        query='Summarize the main functionalities by analyzing Python files.',
        extensions=['py']
    )

    Args:
        ctx (AnyContext): The execution context.
        path (str): Path to the directory or repository.
        query (str): Clear and specific analysis question or goal.
        extensions (list[str], optional): File extensions to include.
        exclude_patterns (list[str], optional): Glob patterns to exclude.
        extraction_token_threshold (int, optional): Token limit for extraction sub-agent.
        summarization_token_threshold (int, optional): Token limit for summarization sub-agent.

    Returns:
        str: Detailed, markdown-formatted analysis and summary.
    """
    if extraction_token_threshold is None:
        extraction_token_threshold = CFG.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
    if summarization_token_threshold is None:
        summarization_token_threshold = (
            CFG.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
        )
    abs_path = os.path.abspath(os.path.expanduser(path))
    file_metadatas = _get_file_metadatas(abs_path, extensions, exclude_patterns)
    ctx.print(stylize_faint("  📝 Extraction"), plain=True)
    extracted_infos = await _extract_info(
        ctx,
        file_metadatas=file_metadatas,
        query=query,
        token_limit=extraction_token_threshold,
    )
    if len(extracted_infos) == 0:
        raise RuntimeError(
            "No info can be extracted, adjust extensions or exclude_patterns."
        )
    if len(extracted_infos) == 1:
        return extracted_infos[0]
    summarized_infos = extracted_infos
    while len(summarized_infos) > 1:
        ctx.print(stylize_faint("  📝 Summarization"), plain=True)
        summarized_infos = await _summarize_info(
            ctx,
            extracted_infos=summarized_infos,
            query=query,
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
            try:
                rel_path = os.path.relpath(file_path, dir_path)
                if is_excluded(rel_path, exclude_patterns):
                    continue
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    metadata_list.append({"path": rel_path, "content": f.read()})
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
    metadata_list.sort(key=lambda m: m["path"])
    return metadata_list


async def _extract_info(
    ctx: AnyContext,
    file_metadatas: list[dict[str, str]],
    query: str,
    token_limit: int,
) -> list[str]:
    extract = create_sub_agent_tool(
        tool_name="extract",
        tool_description="extract",
        system_prompt=CFG.LLM_REPO_EXTRACTOR_SYSTEM_PROMPT,
        auto_summarize=False,
        remember_history=False,
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
                prompt = json.dumps(_create_extract_info_prompt(query, content_buffer))
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
        prompt = json.dumps(_create_extract_info_prompt(query, content_buffer))
        extracted_info = await extract(
            ctx, llm_rate_limitter.clip_prompt(prompt, token_limit)
        )
        extracted_infos.append(extracted_info)
    return extracted_infos


def _create_extract_info_prompt(query: str, content_buffer: list[dict]) -> dict:
    return {
        "main_assistant_query": query,
        "files": content_buffer,
    }


async def _summarize_info(
    ctx: AnyContext,
    extracted_infos: list[str],
    query: str,
    token_limit: int,
) -> list[str]:
    summarize = create_sub_agent_tool(
        tool_name="extract",
        tool_description="extract",
        system_prompt=CFG.LLM_REPO_SUMMARIZER_SYSTEM_PROMPT,
        auto_summarize=False,
        remember_history=False,
    )
    summarized_infos = []
    content_buffer = ""
    for extracted_info in extracted_infos:
        new_prompt = content_buffer + extracted_info
        if llm_rate_limitter.count_token(new_prompt) > token_limit:
            if content_buffer:
                prompt = json.dumps(
                    _create_summarize_info_prompt(query, content_buffer)
                )
                summarized_info = await summarize(
                    ctx, llm_rate_limitter.clip_prompt(prompt, token_limit)
                )
                summarized_infos.append(summarized_info)
            content_buffer = extracted_info
        else:
            content_buffer += extracted_info + "\n"

    # Process any remaining content in the buffer
    if content_buffer:
        prompt = json.dumps(_create_summarize_info_prompt(query, content_buffer))
        summarized_info = await summarize(
            ctx, llm_rate_limitter.clip_prompt(prompt, token_limit)
        )
        summarized_infos.append(summarized_info)
    return summarized_infos


def _create_summarize_info_prompt(query: str, content_buffer: str) -> dict:
    return {
        "main_assistant_query": query,
        "extracted_info": content_buffer,
    }
