import fnmatch
import json
import os
from typing import Any

from zrb.config.config import CFG
from zrb.llm.agent.agent import create_agent, run_agent
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.tool.file import DEFAULT_EXCLUDED_PATTERNS

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


async def analyze_code(
    path: str,
    query: str,
    extensions: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> str:
    """
    Analyzes a code repository or directory to answer a specific query.
    Uses a map-reduce approach: extracts info from files in chunks, then summarizes.

    Args:
        path (str): Path to the directory or repository.
        query (str): Clear and specific analysis question or goal.
        extensions (list[str], optional): File extensions to include.
        exclude_patterns (list[str], optional): Glob patterns to exclude.

    Returns:
        str: Detailed analysis and summary.
    """
    if extensions is None:
        extensions = _DEFAULT_EXTENSIONS
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDED_PATTERNS

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: Path not found: {path}"

    # 1. Gather files
    file_metadatas = _get_file_metadatas(abs_path, extensions, exclude_patterns)
    if not file_metadatas:
        return "No files found matching the criteria."

    print(f"  📝 Extraction ({len(file_metadatas)} files)")

    # 2. Extract Info
    extraction_token_threshold = CFG.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
    extracted_infos = await _extract_info(
        file_metadatas=file_metadatas,
        query=query,
        token_limit=extraction_token_threshold,
    )

    if not extracted_infos:
        return "No information could be extracted from the files."

    if len(extracted_infos) == 1:
        return extracted_infos[0]

    # 3. Summarize Info (Reduce)
    summarization_token_threshold = CFG.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
    summarized_infos = extracted_infos

    while len(summarized_infos) > 1:
        print(f"  📝 Summarization ({len(summarized_infos)} chunks)")
        summarized_infos = await _summarize_info(
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
                if _is_excluded(rel_path, exclude_patterns):
                    continue
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    metadata_list.append({"path": rel_path, "content": f.read()})
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
    metadata_list.sort(key=lambda m: m["path"])
    return metadata_list


def _is_excluded(name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        parts = name.split(os.path.sep)
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


async def _extract_info(
    file_metadatas: list[dict[str, str]],
    query: str,
    token_limit: int,
) -> list[str]:
    agent = create_agent(
        model=CFG.LLM_MODEL,
        system_prompt=CFG.LLM_REPO_EXTRACTOR_SYSTEM_PROMPT,
    )

    extracted_infos = []
    content_buffer = []
    current_token_count = 0

    # We estimate token count of the prompt template overhead
    base_overhead = 100

    for metadata in file_metadatas:
        path = metadata.get("path", "")
        content = metadata.get("content", "")
        file_obj = {"path": path, "content": content}
        file_str = json.dumps(file_obj)
        file_tokens = llm_limiter.count_tokens(file_str)

        if current_token_count + file_tokens + base_overhead > token_limit:
            if content_buffer:
                await _run_extraction(agent, query, content_buffer, extracted_infos)

            content_buffer = [file_obj]
            current_token_count = file_tokens
        else:
            content_buffer.append(file_obj)
            current_token_count += file_tokens

    # Process remaining buffer
    if content_buffer:
        await _run_extraction(agent, query, content_buffer, extracted_infos)

    return extracted_infos


async def _run_extraction(agent, query, content_buffer, extracted_infos):
    prompt_data = {
        "main_assistant_query": query,
        "files": content_buffer,
    }
    # We serialize to JSON for the prompt
    message = json.dumps(prompt_data)

    result, _ = await run_agent(
        agent=agent,
        message=message,
        message_history=[],  # Stateless
        limiter=llm_limiter,
    )
    extracted_infos.append(str(result))


async def _summarize_info(
    extracted_infos: list[str],
    query: str,
    token_limit: int,
) -> list[str]:
    agent = create_agent(
        model=CFG.LLM_MODEL,
        system_prompt=CFG.LLM_REPO_SUMMARIZER_SYSTEM_PROMPT,
    )

    summarized_infos = []
    content_buffer = ""
    # Overhead for prompt structure
    base_overhead = 100

    for info in extracted_infos:
        # Check if adding this info exceeds limit
        if (
            llm_limiter.count_tokens(content_buffer + info) + base_overhead
            > token_limit
        ):
            if content_buffer:
                await _run_summarization(agent, query, content_buffer, summarized_infos)
            content_buffer = info
        else:
            content_buffer += info + "\n"

    if content_buffer:
        await _run_summarization(agent, query, content_buffer, summarized_infos)

    return summarized_infos


async def _run_summarization(agent, query, content_buffer, summarized_infos):
    prompt_data = {
        "main_assistant_query": query,
        "extracted_info": content_buffer,
    }
    message = json.dumps(prompt_data)

    result, _ = await run_agent(
        agent=agent,
        message=message,
        message_history=[],  # Stateless
        limiter=llm_limiter,
    )
    summarized_infos.append(str(result))
