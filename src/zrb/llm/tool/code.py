import fnmatch
import json
import os

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.agent import create_agent, run_agent
from zrb.llm.config.config import llm_config
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.prompt.prompt import (
    get_repo_extractor_system_prompt,
    get_repo_summarizer_system_prompt,
)
from zrb.llm.tool.file import DEFAULT_EXCLUDED_PATTERNS
from zrb.util.file import is_path_excluded

# LSP integration for semantic pre-analysis
from zrb.llm.lsp.manager import lsp_manager

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

# File extensions that LSP can analyze semantically
_LSP_SUPPORTED_EXTENSIONS = {
    ".py", ".pyi", ".pyw",      # Python
    ".go",                       # Go
    ".ts", ".tsx", ".js", ".jsx", # TypeScript/JavaScript
    ".rs",                       # Rust
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",  # C/C++
    ".rb", ".rake", ".gemspec",  # Ruby
    ".java",                     # Java
    ".php",                      # PHP
    ".cs",                       # C#
    ".swift",                    # Swift
    ".kt", ".kts",               # Kotlin
    ".scala", ".sc",             # Scala
    ".lua",                      # Lua
}


async def _get_lsp_context(file_path: str, abs_dir: str) -> dict | None:
    """Get LSP semantic context for a file (symbols + diagnostics).
    
    Returns structured data about the file without reading its content.
    More token-efficient than reading the whole file for structure queries.
    """
    try:
        full_path = os.path.join(abs_dir, file_path)
        
        # Get document symbols
        symbols_result = await lsp_manager.get_document_symbols(full_path)
        
        # Get diagnostics (errors, warnings)
        diagnostics_result = await lsp_manager.get_diagnostics(full_path)
        
        if not symbols_result.get("found") and not diagnostics_result.get("found"):
            return None
        
        context = {
            "path": file_path,
            "lsp_symbols": [],
            "lsp_diagnostics": [],
        }
        
        # Format symbols (compact representation)
        if symbols_result.get("found"):
            for sym in symbols_result.get("symbols", [])[:50]:  # Limit to 50 symbols
                context["lsp_symbols"].append({
                    "name": sym.get("name"),
                    "kind": sym.get("kind"),
                    "line": sym.get("line"),
                })
        
        # Format diagnostics
        if diagnostics_result.get("found") and diagnostics_result.get("count", 0) > 0:
            for diag in diagnostics_result.get("diagnostics", [])[:20]:  # Limit to 20
                context["lsp_diagnostics"].append({
                    "severity": diag.get("severity"),
                    "message": diag.get("message"),
                    "line": diag.get("line"),
                })
        
        return context
        
    except Exception as e:
        # LSP not available or error - return None to fall back to file reading
        zrb_print(f"  LSP context error for {file_path}: {e}", plain=True)
        return None


async def analyze_code(
    path: str,
    query: str,
    file_pattern: str | None = None,
    exclude_patterns: list[str] | None = None,
    use_lsp: bool = True,
) -> str:
    """
    Semantic analysis of a directory using an LLM sub-agent.

    Automatically excludes common directories (`.git`, `node_modules`, `__pycache__`, etc.).
    When `file_pattern=None`, intelligently detects project type and scans appropriately.
    File contents are automatically truncated to token limits.

    MANDATES:
    - SLOW and resource-intensive (uses LLM sub-agent).
    - For single file analysis, use `AnalyzeFile` instead.
    - For simple file listing, use `LS` or `Glob`.
    - Use `file_pattern` parameter to limit search scope (e.g., `*.py` for Python files).
    - Use `exclude_patterns` parameter to override default exclusions (e.g., `[]` to include all files).

    LSP INTEGRATION:
    - When use_lsp=True (default), uses LSP for semantic pre-analysis on supported file types.
    - More token-efficient than reading full file content for structure queries.
    - Provides symbol names, types, and locations without reading entire files.
    - Falls back to file reading when LSP is unavailable.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: Path not found: {path}"

    extensions = _DEFAULT_EXTENSIONS
    exclude_patterns = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDED_PATTERNS
    )

    include_patterns = None
    if file_pattern is not None:
        if file_pattern.startswith("*."):
            ext = file_pattern[2:]
            if ext in extensions:
                extensions = [ext]
            else:
                include_patterns = [file_pattern]
        else:
            include_patterns = [file_pattern]

    # Use LSP-enhanced file metadata collection when available
    if use_lsp:
        # Check if any LSP servers are available
        available_servers = lsp_manager.list_available_servers()
        if available_servers:
            zrb_print(f"  🔍 LSP enabled (servers: {list(available_servers.keys())})", plain=True)
            file_metadatas = await _get_file_metadatas_with_lsp(
                abs_path, extensions, include_patterns, exclude_patterns
            )
        else:
            zrb_print("  📄 LSP not available, using file reading", plain=True)
            file_metadatas = _get_file_metadatas(
                abs_path, extensions, include_patterns, exclude_patterns
            )
    else:
        file_metadatas = _get_file_metadatas(
            abs_path, extensions, include_patterns, exclude_patterns
        )
    
    # Shutdown LSP servers to free resources
    if use_lsp:
        await lsp_manager.shutdown_all()

    if not file_metadatas:
        return "No files found matching the criteria. [SYSTEM SUGGESTION]: Try using a different file_pattern or check if the directory contains code files."

    zrb_print(f"\n  📝 Extraction ({len(file_metadatas)} files)", plain=True)

    extraction_token_threshold = CFG.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
    extracted_infos = await _extract_info(
        file_metadatas=file_metadatas,
        query=query,
        token_limit=extraction_token_threshold,
        use_lsp=use_lsp,
    )

    if not extracted_infos:
        return "No information could be extracted from the files. [SYSTEM SUGGESTION]: Try rephrasing your query to be more specific about what you're looking for."

    if len(extracted_infos) == 1:
        return extracted_infos[0]

    summarization_token_threshold = CFG.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
    summarized_infos = extracted_infos

    while len(summarized_infos) > 1:
        zrb_print(f"\n  📝 Summarization ({len(summarized_infos)} chunks)", plain=True)
        summarized_infos = await _summarize_info(
            extracted_infos=summarized_infos,
            query=query,
            token_limit=summarization_token_threshold,
        )

    return summarized_infos[0]


def _get_file_metadatas(
    dir_path: str,
    extensions: list[str],
    include_patterns: list[str] | None,
    exclude_patterns: list[str],
    use_lsp: bool = False,
) -> list[dict[str, str]]:
    """Get file metadata for analysis.
    
    Args:
        dir_path: Directory path to scan
        extensions: File extensions to include
        include_patterns: Patterns to include
        exclude_patterns: Patterns to exclude
        use_lsp: Whether to use LSP for semantic analysis (async, needs to be called separately)
    
    Returns:
        List of file metadata dicts
    """
    metadata_list = []
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [
            d for d in dirs if not any(pattern in d for pattern in exclude_patterns)
        ]
        files.sort()
        for file in files:
            if not any(file.endswith(f".{ext}") for ext in extensions):
                continue
            file_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(file_path, dir_path)
                if is_path_excluded(rel_path, exclude_patterns):
                    continue
                if include_patterns and not _is_path_included(
                    rel_path, include_patterns
                ):
                    continue
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    metadata_list.append({"path": rel_path, "content": f.read()})
            except Exception as e:
                zrb_print(f"Error reading file {file_path}: {e}", plain=True)
    metadata_list.sort(key=lambda m: m["path"])
    return metadata_list


async def _get_file_metadatas_with_lsp(
    dir_path: str,
    extensions: list[str],
    include_patterns: list[str] | None,
    exclude_patterns: list[str],
) -> list[dict[str, str | dict]]:
    """Get file metadata with LSP semantic context when available.
    
    This is more token-efficient than reading full file content for structure queries.
    Falls back to reading file content if LSP is not available for the file type.
    """
    import asyncio
    
    metadata_list = []
    lsp_tasks = []
    file_paths = []
    
    # First pass: collect files and start LSP tasks for supported file types
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [
            d for d in dirs if not any(pattern in d for pattern in exclude_patterns)
        ]
        files.sort()
        for file in files:
            if not any(file.endswith(f".{ext}") for ext in extensions):
                continue
            file_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(file_path, dir_path)
                if is_path_excluded(rel_path, exclude_patterns):
                    continue
                if include_patterns and not _is_path_included(
                    rel_path, include_patterns
                ):
                    continue
                
                # Check if LSP supports this file type
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in _LSP_SUPPORTED_EXTENSIONS:
                    # Queue LSP analysis (async)
                    lsp_tasks.append(_get_lsp_context(rel_path, dir_path))
                    file_paths.append(rel_path)
                else:
                    # Read file content directly (non-LSP file type)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        metadata_list.append({"path": rel_path, "content": f.read()})
                        
            except Exception as e:
                zrb_print(f"Error reading file {file_path}: {e}", plain=True)
    
    # Run all LSP tasks concurrently
    if lsp_tasks:
        zrb_print(f"  🔍 LSP analysis ({len(lsp_tasks)} files)", plain=True)
        lsp_results = await asyncio.gather(*lsp_tasks, return_exceptions=True)
        
        for rel_path, lsp_result in zip(file_paths, lsp_results):
            if isinstance(lsp_result, Exception):
                # LSP failed - fall back to reading file
                try:
                    with open(os.path.join(dir_path, rel_path), "r", encoding="utf-8", errors="ignore") as f:
                        metadata_list.append({"path": rel_path, "content": f.read()})
                except Exception:
                    pass
            elif lsp_result and lsp_result.get("lsp_symbols"):
                # Use LSP context (more token-efficient for structure queries)
                metadata_list.append(lsp_result)
            else:
                # No LSP data - read file content
                try:
                    with open(os.path.join(dir_path, rel_path), "r", encoding="utf-8", errors="ignore") as f:
                        metadata_list.append({"path": rel_path, "content": f.read()})
                except Exception:
                    pass
    
    metadata_list.sort(key=lambda m: m["path"])
    return metadata_list


def _is_path_included(name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        parts = name.split(os.path.sep)
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


async def _extract_info(
    file_metadatas: list[dict[str, str | dict]],
    query: str,
    token_limit: int,
    use_lsp: bool = False,
) -> list[str]:
    agent = create_agent(
        model=llm_config.model,
        system_prompt=get_repo_extractor_system_prompt(),
    )

    extracted_infos = []
    content_buffer = []
    current_token_count = 0

    # We estimate token count of the prompt template overhead
    base_overhead = 100

    for metadata in file_metadatas:
        path = metadata.get("path", "")
        
        # Handle LSP context format vs raw content
        if "lsp_symbols" in metadata:
            # LSP semantic context (more compact)
            content = json.dumps({
                "path": path,
                "symbols": metadata.get("lsp_symbols", []),
                "diagnostics": metadata.get("lsp_diagnostics", []),
                "note": "LSP semantic context - symbol names, types, and locations"
            })
        else:
            # Raw file content
            content = metadata.get("content", "")
            content = json.dumps({"path": path, "content": content})
        
        file_tokens = llm_limiter.count_tokens(content)

        if current_token_count + file_tokens + base_overhead > token_limit:
            if content_buffer:
                await _run_extraction(agent, query, content_buffer, extracted_infos)

            content_buffer = [content]
            current_token_count = file_tokens
        else:
            content_buffer.append(content)
            current_token_count += file_tokens

    # Process remaining buffer
    if content_buffer:
        await _run_extraction(agent, query, content_buffer, extracted_infos)

    return extracted_infos


async def _run_extraction(agent, query, content_buffer, extracted_infos):
    prompt_data = {
        "main_assistant_query": query,
        "files": content_buffer,  # List of JSON strings (either LSP context or raw content)
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
        model=llm_config.model,
        system_prompt=get_repo_summarizer_system_prompt(),
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


analyze_code.__name__ = "AnalyzeCode"
