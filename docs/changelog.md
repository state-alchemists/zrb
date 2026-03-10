🔖 [Documentation Home](../README.md)

## 2.8.4 (March 10, 2026)

- **Fix: Windows Encoding Error in Journal Index Reading**:
  - **UTF-8 Encoding Fix**: Added explicit `encoding="utf-8"` to journal index file reading in `src/zrb/llm/prompt/prompt.py` to prevent `UnicodeDecodeError` on Windows where the default encoding is `cp1252`.
  - **Shell History Encoding**: Added explicit `encoding="utf-8"` to shell history file reading in `src/zrb/llm/app/completion.py` for consistent cross-platform behavior.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.8.4 in `pyproject.toml`.


## 2.8.3 (March 10, 2026)

- **Fix: Windows Terminal Size Detection**:
  - **Robust Terminal Size Utility**: Added `src/zrb/util/cli/terminal.py` with `get_terminal_size()` function that gracefully handles terminal size detection across platforms, especially Windows where standard methods fail when stdout is redirected.
  - **Windows CONOUT$ Support**: Enhanced `get_original_stdout()` in `src/zrb/llm/app/redirection.py` to use Windows `CONOUT$` device for more reliable terminal access when file descriptors are redirected.
  - **UI Crash Prevention**: Wrapped `output.get_size()` in `src/zrb/llm/app/ui.py` with a robust fallback that prevents crashes on Windows when prompt_toolkit cannot detect console dimensions.
  - **Multi-Method Detection**: Terminal size detection now tries `sys.__stdout__`, `sys.__stderr__`, `sys.__stdin__`, Windows `CONOUT$`, and finally falls back to `shutil.get_terminal_size()` with environment variable support.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.8.3 in `pyproject.toml`.


## 2.8.2 (March 7, 2026)

- **Documentation: Configuration Default Value Corrections**:
  - **Environment Variable Defaults**: Fixed incorrect default values in configuration documentation:
    - `ZRB_WARN_UNRECOMMENDED_COMMAND`: Corrected default from `"1"` to `"on"` (true)
    - `ZRB_USE_TIKTOKEN`: Corrected default from `"1"` to `"off"` (false)
    - `ZRB_LLM_MODEL`: Clarified default is `"openai:gpt-4o"` when unset (via `llm_config.py`)
    - `ZRB_LLM_SMALL_MODEL`: Updated to indicate it falls back to main model instead of `"gpt-4o-mini"`
  - **ASCII Art Configuration**: Clarified that `ZRB_LLM_ASSISTANT_ASCII_ART` refers to the ASCII art name, not the content itself.

- **Configuration: ASCII Art Directory Rename**:
  - **Directory Path Change**: Renamed default `ASCII_ART_DIR` from `.zrb/llm/prompt` to `.zrb/ascii-art` to avoid confusion with `LLM_PROMPT_DIR`.
  - **Code Update**: Modified `src/zrb/config/config.py` to use the new directory path for ASCII art file storage.
  - **Documentation Sync**: Updated `docs/configuration/llm-config.md` to reflect the new default directory location.

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

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)

