🔖 [Documentation Home](../README.md)

## 2.8.0 (March 6, 2026)

- **Breaking: FastApp Removal**:
  - **Deprecation**: Removed the entire FastApp module (`src/zrb/builtin/project/add/fastapp/`) and project creation task (`src/zrb/builtin/project/create/project_task.py`). FastApp was a legacy feature that is no longer actively maintained.
  - **Code Modification Utilities Removed**: Deleted the `src/zrb/util/codemod/` directory containing AST-based code modification utilities (`modify_class.py`, `modify_method.py`, `modify_function.py`, etc.) that were exclusively used by FastApp.
  - **Dependency Cleanup**: Removed FastApp-related dependencies from `pyproject.toml`:
    - Removed `libcst` from core dependencies
    - Removed `alembic` from dev dependencies
    - Removed `sqlmodel` from dev dependencies
  - **Module Exports Updated**: Removed `add_fastapp_to_project` and `create_project` from `src/zrb/builtin/__init__.py` exports.
  - **Tests Removed**: Deleted all FastApp-related test files (`test/builtin/test_fastapp_task.py`, `test/builtin/test_fastapp_util.py`, and all codemod tests).

- **Compatibility: Python 3.14+ Support**:
  - **Event Loop API Fix**: Changed `asyncio.get_event_loop()` to `asyncio.get_running_loop()` in `src/zrb/llm/hook/executor.py` and test files (`test/task/test_http_check.py`, `test/task/test_tcp_check.py`). The deprecated `get_event_loop()` raises `RuntimeError` in Python 3.14+ when no loop is running.
  - **Free-Threaded Python Safety**: Added thread-safe singleton pattern with `threading.Lock` for hook executor initialization in `src/zrb/llm/hook/executor.py`, ensuring atomic initialization for free-threaded Python (no-GIL) builds.
  - **Version Requirement**: Updated Python version from `>=3.11.0,<3.14.0` to `>=3.11.0,<3.15.0` in `pyproject.toml`.
  - **Python Version File**: Added `.python-version` file specifying Python 3.14 for development environment.

- **Platform: Windows Installation Support**:
  - **PowerShell Installation Script**: Added `install.ps1` script for Windows users with guided installation process including:
    - Python detection with installation guidance
    - Optional Poetry installation
    - Optional virtual environment creation at `~/.local-venv`
    - PowerShell profile registration for automatic venv activation
    - User-level PATH management
  - **Installation Documentation**: Added comprehensive Windows installation section to `docs/installation/installation.md` covering:
    - Multiple Python installation methods (winget, python.org, Microsoft Store)
    - Script execution instructions
    - Manual installation alternatives
    - Windows-specific notes (PowerShell profile locations, activation scripts)

- **Dependency: VoyageAI Python 3.14 Constraint**:
  - Added `python = "<3.14"` constraint for voyageai optional dependency in `pyproject.toml` since the package doesn't yet support Python 3.14.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.8.0 in `pyproject.toml`.


## 2.7.2 (March 6, 2026)

- **Compatibility: Cross-Platform UTF-8 Encoding**:
  - **Explicit UTF-8 Encoding**: Added `encoding="utf-8"` parameter to all file operations across the codebase to ensure consistent behavior across different operating systems, particularly Windows where the default encoding is cp1252.
  - **Files Updated**:
    - `src/zrb/util/file.py`: Core file writing utility
    - `src/zrb/llm/tool/rag.py`: RAG hash file operations (both read and write)
    - `src/zrb/llm/tool/bash.py`: Background PID collection
    - `src/zrb/llm/hook/manager.py`: Hook configuration file loading
    - `src/zrb/llm/tool_call/response_handler/default.py`: Content editor response handler
    - `src/zrb/llm/tool_call/response_handler/replace_in_file_response_handler.py`: Replace-in-file response handler
    - `llm-challenges/runner.py`: Log file writing

- **Testing: Unicode and Emoji Support**:
  - **New Test Coverage**: Added `test_write_file_unicode_emoji()` to verify that `write_file()` properly handles unicode characters, emoji, and special characters (e.g., café, naïve, résumé, 🐭, 🎉, 你好世界).
  - **Test Modernization**: Updated existing `test_write_file_mode()` to use explicit UTF-8 encoding for consistency.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.7.2 in `pyproject.toml`.


## 2.7.1 (March 6, 2026)

- **Performance: Battery Drain Reduction & UI Optimization**:
  - **Reduced CPU Usage**: Significantly decreased UI refresh frequency from 0.05s to 0.5s (`refresh_interval=0.5`) in `src/zrb/llm/app/ui.py`, reducing continuous CPU consumption during idle periods.
  - **Optimized System Info Updates**: Changed system information (CWD and Git status) update frequency from every 2 seconds to every 60 seconds, eliminating unnecessary background polling.
  - **Improved Output Scrolling**: Reduced output scrolling check frequency from 0.1s to 5.0s, minimizing UI thread activity.
  - **Refactored Update Logic**: Extracted system info update into dedicated `_update_system_info()` method and added initial update on UI startup for better responsiveness.

- **Reliability: Tool Call & MCP Server Retry Mechanisms**:
  - **Function Toolset Retry**: Added `max_retries=3` parameter to `FunctionToolset` initialization in `src/zrb/llm/agent/common.py` to handle transient tool execution failures gracefully.
  - **MCP Server Retry Support**: Enhanced MCP server creation in `src/zrb/llm/tool/mcp.py` with retry capabilities:
    - Added `max_retries=3` to `MCPServerStdio` instances for stdio-based servers
    - Added `max_retries=3` to `MCPServerSSE` instances for SSE-based servers
  - **Post-Task System Updates**: Added `await self._update_system_info()` calls after LLM task completion to ensure UI reflects current system state.


## 2.7.0 (March 5, 2026)

- **Major: Core Prompt System Simplification & Mandate Restructuring**:
  - **Project Context Prompt Overhaul**: Completely redesigned `src/zrb/llm/prompt/claude.py` to provide clear "Project Documentation Guidelines" instead of attempting to summarize documentation files. The new approach lists available documentation files with status indicators and provides SMART documentation usage rules for LLMs.
  - **Mandate Simplification**: Streamlined all core mandate files with clearer, more direct language:
    - **Git Mandate**: Restructured as "🐙 Absolute Git Rule" with clear prohibitions, approval protocol, and violation response. Removed verbose examples in favor of concise, actionable rules.
    - **Journal Mandate**: Restructured as "📓 Absolute Journaling Rule" with clear activation requirements, smart reading guidelines, and update guidelines. Emphasizes journal as single source of truth.
    - **Core Mandate**: Reorganized into clear "Core Directives" focusing on Plan Before Acting, Context-First, Empirical Verification, Clarify Intent, Context Efficiency, Secret Protection, and Self-Correction.
  - **Prompt Placeholder Enhancement**: Updated `src/zrb/llm/prompt/prompt.py` to include file existence status indicators (`{CFG_LLM_JOURNAL_DIR_STATUS}` and `{CFG_LLM_JOURNAL_INDEX_FILE_STATUS}`) and improved journal content handling with truncation for large files.

- **Improvement: Summarizer Configuration Simplification**:
  - **Default History Processor**: Simplified summarizer usage across the system by removing explicit token threshold and summary window parameters in favor of default configuration. Updated `src/zrb/builtin/llm/chat.py`, `src/zrb/llm/agent/manager.py`, and `src/zrb/llm/task/llm_chat_task.py` to use `create_summarizer_history_processor()` without parameters.
  - **History Splitter Logic Update**: Modified `src/zrb/llm/summarizer/history_splitter.py` to use `summary_window` parameter directly instead of calculating retention ratio, improving clarity and consistency.

- **Cleanup: Removal of Unused Thinking Tag Utilities**:
  - **Code Removal**: Removed `src/zrb/util/string/thinking.py` and `test/util/string/test_thinking.py` as the thinking tag removal functionality was no longer being used in `src/zrb/llm/task/llm_task.py`.
  - **Simplified Output Processing**: Updated `LLMTask._clean_output()` to only remove ANSI escape codes, eliminating unnecessary processing step for thinking tags.

- **Dependency Updates**:
  - **Core Framework**: pydantic-ai-slim updated from ~1.63.0 to ~1.65.0, bringing latest improvements and bug fixes from the pydantic-ai framework.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.7.0 in `pyproject.toml`, marking a significant release with major prompt system improvements.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)

