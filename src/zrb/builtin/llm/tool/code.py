import os

from zrb.builtin.llm.tool.file import DEFAULT_EXCLUDED_PATTERNS, is_excluded
from zrb.builtin.llm.tool.sub_agent import create_sub_agent_tool
from zrb.context.any_context import AnyContext

_EXTRACT_INFO_SYSTEM_PROMPT = """
You are an extraction info agent.
Your goal is to help to extract relevant information to help the main LLM Agent.
You write your output is in markdown format containing path and relevant information.
Extract only information that relevant to main LLM Agent's goal.

Extracted Information format (Use this as reference, extract relevant information only):
# <file-name>
## imports
- <imported-package>
- ...
## variables
- <variable-type> <variable-name>: <the-purpose-of-the-variable>
- ...
## functions
- <function-name>:
  - parameters: <parameters>
  - logic/description: <what-the-function-do-and-how-it-works>
...
# <other-file-name>
...
""".strip()


_SUMMARIZE_INFO_SYSTEM_PROMPT = """
You are an information summarization agent.
Your goal is to summarize information to help the main LLM Agent.
The summarization result should contains all necessary details
to help main LLM Agent achieve the goal.
"""

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
    extraction_char_limit: int = 150000,
    summarization_char_limit: int = 150000,
) -> str:
    """
    Extract and summarize information from a directory that probably
    contains a large resources.
    You should state the goal specifically so that the tool can return relevant informations.
    Use this tool for:
    - summarization
    - outline/structure extraction
    - code review
    - create diagram as code
    - other tasks
    Args:
        path (str): File path to be analyze. Pass exactly as provided, including '~'.
        goal(str): Goal of extracting information (for example creating C4 diagram)
        extensions(Optional[list[str]]): List of extension to be included
            while reading resources. Defaults to common programming languages and config files.
        exclude_patterns(Optional[list[str]]): List of patterns to exclude from analysis.
            Common patterns like '.venv', 'node_modules' should be excluded by default.
        extraction_char_limit(Optional[int]): Max resource content char length
            the extraction assistant able to handle. Defaults to 150000
        summarization_char_limit(Optional[int]): Max resource content char length
            the summarization assistant able to handle. Defaults to 150000
    Returns:
        str: The analysis result
    Raises:
        Exception: If an error occurs.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    file_metadatas = _get_file_metadatas(abs_path, extensions, exclude_patterns)
    ctx.print("Extraction")
    extracted_infos = await _extract_info(
        ctx,
        file_metadatas=file_metadatas,
        goal=goal,
        char_limit=extraction_char_limit,
    )
    ctx.print("Summarization")
    summarized_infos = await _summarize_info(
        ctx,
        extracted_infos=extracted_infos,
        goal=goal,
        char_limit=summarization_char_limit,
    )
    while len(summarized_infos) > 1:
        ctx.print("Summarization")
        summarized_infos = await _summarize_info(
            ctx,
            extracted_infos=summarized_infos,
            goal=goal,
            char_limit=summarization_char_limit,
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
    char_limit: int,
) -> list[str]:
    extract = create_sub_agent_tool(
        tool_name="extract",
        tool_description="extract",
        system_prompt=_EXTRACT_INFO_SYSTEM_PROMPT,
    )
    extracted_infos = []
    content_buffer = ""
    for metadata in file_metadatas:
        path = metadata.get("path", "")
        content = metadata.get("content", "")
        metadata_str = f"Path: {path}\nContent: {content}"
        if len(content_buffer) + len(metadata_str) > char_limit:
            if content_buffer:
                prompt = _create_extract_info_prompt(goal, content_buffer)
                extracted_info = await extract(ctx, prompt)
                extracted_infos.append(extracted_info)
            content_buffer = metadata_str
        else:
            content_buffer += metadata_str + "\n"

    # Process any remaining content in the buffer
    if content_buffer:
        prompt = _create_extract_info_prompt(goal, content_buffer)
        extracted_info = await extract(ctx, prompt)
        extracted_infos.append(extracted_info)
    return extracted_infos


def _create_extract_info_prompt(goal: str, content_buffer: str) -> str:
    return f"# Main LLM Agent Goal\n{goal}\n# Files\n{content_buffer}"


async def _summarize_info(
    ctx: AnyContext,
    extracted_infos: list[str],
    goal: str,
    char_limit: int,
) -> list[str]:
    summarize = create_sub_agent_tool(
        tool_name="extract",
        tool_description="extract",
        system_prompt=_SUMMARIZE_INFO_SYSTEM_PROMPT,
    )
    summarized_infos = []
    content_buffer = ""
    for extracted_info in extracted_infos:
        if len(content_buffer) + len(extracted_info) > char_limit:
            if content_buffer:
                prompt = _create_summarize_info_prompt(goal, content_buffer)
                summarized_info = await summarize(ctx, prompt)
                summarized_infos.append(summarized_info)
            content_buffer = extracted_info
        else:
            content_buffer += extracted_info + "\n"

    # Process any remaining content in the buffer
    if content_buffer:
        prompt = _create_summarize_info_prompt(goal, content_buffer)
        summarized_info = await summarize(ctx, prompt)
        summarized_infos.append(summarized_info)
    return summarized_infos


def _create_summarize_info_prompt(goal: str, content_buffer: str) -> str:
    return f"# Main LLM Agent Goal\n{goal}\n# Extracted Info\n{content_buffer}"
