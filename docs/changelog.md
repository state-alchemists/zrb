🔖 [Documentation Home](../README.md)

## 2.8.3 (March 10, 2026)

- **Fix: Windows Terminal Size Detection**:
  - **Robust Terminal Size Utility**: Added `src/zrb/util/cli/terminal.py` with `get_terminal_size()` function that gracefully handles terminal size detection across platforms, especially Windows where standard methods fail when stdout is redirected.
  - **Windows CONOUT$ Support**: Enhanced `get_original_stdout()` in `src/zrb/llm/app/redirection.py` to use Windows `CONOUT$` device for more reliable terminal access when file descriptors are redirected.
  - **UI Crash Prevention**: Wrapped `output.get_size()` in `src/zrb/llm/app/ui.py` with a robust fallback that prevents crashes on Windows when prompt_toolkit cannot detect console dimensions.
  - **Multi-Method Detection**: Terminal size detection now tries `sys.__stdout__`, `sys.__stderr__`, `sys.__stdin__`, Windows `CONOUT$`, and finally falls back to `shutil.get_terminal_size()` with environment variable support.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.8.3 in `pyproject.toml`.


## 2.8.2 (March 9, 2026)

- **Configuration: Default Value Updates**:
  - **LLM Model Defaults**: Updated documentation to reflect that `ZRB_LLM_MODEL` now defaults to `openai:gpt-4o` when unset, and `ZRB_LLM_SMALL_MODEL` falls back to `ZRB_LLM_MODEL` instead of having a hardcoded default.
  - **Tiktoken Default Changed**: Changed `ZRB_USE_TIKTOKEN` default from `1` to `off` (false) in documentation, reflecting the actual runtime behavior for better out-of-box experience.
  - **ASCII Art Directory**: Changed default `ZRB_ASCII_ART_DIR` from `.zrb/llm/prompt` to `.zrb/ascii-art` in `src/zrb/config/config.py` for clearer organization and separation of concerns.

- **Documentation Corrections**:
  - **Default Value Fixes**: Corrected several default value descriptions in `docs/configuration/env-vars.md` and `docs/configuration/llm-config.md` to accurately reflect current behavior.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.8.2 in `pyproject.toml`.


## 2.8.1 (March 7, 2026)

- **Fix: Empty Response Filtering for Model Compatibility**:
  - **Empty Response Filter**: Added `_filter_empty_responses()` method to `FileHistoryManager` in `src/zrb/llm/history_manager/file_history_manager.py` to filter out responses with empty or `None` parts from conversation history before loading and saving.
  - **GLM-5 Compatibility**: Empty responses were causing "invalid message content type: <nil>" errors with certain models like GLM-5 via Ollama when the conversation history was sent to the model. This filter prevents those errors by removing empty responses during history loading and saving operations.
  - **Test Coverage**: Added comprehensive test `test_file_history_manager_filter_empty_responses()` in `test/llm/history_manager/test_file_history_manager.py` covering empty responses, `None` parts, and nested structures.

- **Documentation: Comprehensive Documentation Overhaul**:
  - **Table of Contents**: Added navigable Table of Contents to all 19 documentation files with anchor links for improved discoverability.
  - **Quick Reference Tables**: Added quick reference summary tables at the end of each documentation file for fast lookups.
  - **Consistent Navigation**: Added breadcrumb navigation headers (🔖 Documentation Home > Section > Topic) to all documentation pages.
  - **Better Structure**: Reorganized documentation with clearer section hierarchies and improved visual formatting.
  - **Callout Boxes**: Added 💡 Tip and ⚠️ Warning callout boxes throughout documentation to highlight important information.
  - **Enhanced Tables**: Converted dense bullet-point lists to scannable tables in configuration and API reference documents.
  - **Files Updated**:
    - Core Concepts: `cli-and-groups.md`, `inputs.md`, `environments.md`, `session-and-context.md`, `tasks-and-lifecycle.md`
    - Task Types: `basic-tasks.md`, `builtin-helpers.md`, `file-ops.md`, `readiness-checks.md`, `triggers-and-schedulers.md`
    - Advanced Topics: `hooks.md`, `web-ui.md`, `white-labeling.md`, `ci-cd.md`, `claude-compatibility.md`, `llm-integration.md`, `upgrading-guide.md`, `maintainer-guide.md`
    - Configuration: `env-vars.md`, `llm-config.md`
    - Technical Specs: `llm-context.md`
    - Installation: `installation.md`
    - Root: `README.md`

- **Maintenance**:
  - **Version Bump**: Updated to version 2.8.1 in `pyproject.toml`.


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

