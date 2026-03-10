🔖 [Documentation Home](../README.md)

## 2.9.1 (March 10, 2026)

- **Refactor: LLM System Prompt Architecture**:
  - **MECE Compliance**: Restructured prompt files to be Mutually Exclusive, Collectively Exhaustive with zero conflicts and no ambiguity.
  - **mandate.md**: Simplified skill protocol, removed redundant conditions, clarified activation pattern.
  - **journal_mandate.md**: Restructured to Protocol/Prohibitions/Hierarchy format (consistent with git_mandate.md), clarified hierarchy scope.
  - **git_mandate.md**: Already had correct structure (Prohibitions/Protocol/Violation).
  - **Documentation**: Moved older changelog entries (2.8.x) to `docs/changelog-v2.md`.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.9.1 in `pyproject.toml`.

## 2.9.0 (March 10, 2026)

- **Feature: LSP (Language Server Protocol) Support**:
  - **LSP Module**: Added `src/zrb/llm/lsp/` module with full LSP client implementation including `manager.py`, `protocol.py`, `server.py`, and `tools.py`.
  - **IDE-like Code Intelligence**: LLM agents can now use semantic code navigation tools similar to IDEs:
    - `LspFindDefinition`: Find where a symbol (class, function, variable) is defined
    - `LspFindReferences`: Find all references to a symbol across the codebase
    - `LspGetDiagnostics`: Get errors, warnings, and hints for a file
    - `LspGetDocumentSymbols`: Get all symbols defined in a file
    - `LspGetWorkspaceSymbols`: Search for symbols across the entire project
    - `LspGetHoverInfo`: Get type information and documentation at a position
    - `LspRenameSymbol`: Rename a symbol across all files (with dry-run preview)
    - `LspListServers`: Check which LSP servers are installed
  - **Multi-Language Support**: Works with pyright/pylsp (Python), gopls (Go), typescript-language-server (TypeScript/JavaScript), rust-analyzer (Rust), clangd (C/C++), and other LSP-compliant servers.
  - **Documentation**: Added `docs/advanced-topics/lsp-support.md` with setup and usage guide.

- **Feature: Planning/Todo Tools for LLM Agents**:
  - **Todo Manager**: Added `src/zrb/llm/tool/plan.py` with task planning and progress tracking inspired by Deep Agents' write_todos.
  - **Planning Tools**:
    - `WriteTodos`: Create or update a todo list for planning complex multi-step tasks
    - `GetTodos`: Get current todo list and progress summary
    - `UpdateTodo`: Mark todos as pending, in_progress, completed, or cancelled
    - `ClearTodos`: Clear all todos for a session
  - **Per-Session Storage**: Todos are isolated per conversation session and persisted to disk at `~/.zrb/todos/{session_name}.json`, surviving application restarts.
  - **Progress Tracking**: Automatic progress calculation (completed/total, percentage) helps track complex workflows.

- **Feature: Enhanced Code Tools**:
  - **Extended Code Module**: Significantly enhanced `src/zrb/llm/tool/code.py` with additional code manipulation capabilities.
  - **Tool Exports**: Updated `src/zrb/llm/tool/__init__.py` to export planning tools alongside code tools.

- **Feature: Tool Factory Pattern for LLMTask and LLMChatTask**:
  - **LLMTask Tool Factories**: Added `tool_factories` and `toolset_factories` parameters to `LLMTask` in `src/zrb/llm/task/llm_task.py`, allowing tools and toolsets to be resolved dynamically at execution time using the task's own context.
  - **LLMChatTask Factory Context**: `LLMChatTask` factories resolve tools/toolsets using the parent context, enabling access to parent task state (e.g., yolo state from xcom), while the inner `LLMTask` uses its own context for its factories.
  - **AsyncExitStack Management**: Moved `AsyncExitStack` handling from `LLMChatTask` to `LLMTask._exec_action`, ensuring toolset context managers are properly entered for both task types.
  - **Factory Methods**: Added `add_tool_factory`, `append_tool_factory`, `add_toolset_factory`, and `append_toolset_factory` methods to both task classes for fluent API usage.

- **Feature: LSP Tools Registration in LLMChatTask**:
  - **Auto-Registration**: Updated `src/zrb/builtin/llm/chat.py` to automatically include LSP tools and planning tools in the default LLM chat task.

- **Fix: Prompt Toolkit Terminal Size Handling**:
  - **Robust Terminal Utility**: Added `src/zrb/util/cli/terminal.py` with `get_terminal_size()` function that gracefully handles terminal size detection across platforms, particularly Windows where standard methods fail when stdout is redirected.
  - **Windows CONOUT$ Support**: Enhanced `get_original_stdout()` in `src/zrb/llm/app/redirection.py` to use Windows `CONOUT$` device for reliable terminal access when file descriptors are redirected.
  - **UI Crash Prevention**: Wrapped `output.get_size()` in `src/zrb/llm/app/ui.py` with robust fallback handling to prevent crashes when prompt_toolkit cannot detect console dimensions.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.9.0 in `pyproject.toml`.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)

