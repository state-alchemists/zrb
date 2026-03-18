🔖 [Documentation Home](../README.md)

## 2.10.3 (March 18, 2026)

- **Feature: Conversation History Display on Load**:
  - Added `history_formatter.py` utility to format pydantic-ai conversation history as human-readable text.
  - `/load` command now displays loaded conversation history in the UI, matching the streaming style (💬/🤖 icons with timestamps).
  - Format: User messages show `💬 {time} >> {content}`, assistant messages show `🤖 {time} >>` with indented content.
  - Tool calls/returns shown inline with 🧰/🔠 icons.

- **Feature: Timestamped Session Backups**:
  - `FileHistoryManager.save()` now creates timestamped backup files in addition to the main session file.
  - Backup naming: `<session-name>-YYYY-MM-DD-HH-MM-SS.json` (with sequence numbers for conflicts).
  - Session names with existing timestamps are normalized (base name extracted) for cleaner backup file names.

- **Feature: Save Command Autocomplete**:
  - `/save` command autocomplete now shows existing session names (labeled "Existing Session") for easy overwriting.
  - Also shows timestamp-based name (labeled "New Session") for creating new sessions.

- **Security: CVE-2026-23491 (pyasn1 DoS Vulnerability)**:
  - Fixed uncontrolled recursion vulnerability in `pyasn1` (transitive dependency via `google-auth`).
  - Added explicit `pyasn1 >= 0.6.3` constraint to enforce patched version.
  - Vulnerability: Crafted ASN.1 payloads could cause DoS via recursion crash or OOM.

- **Refactor: Improved Test Coverage**:
  - Added comprehensive tests for `history_formatter.py`, `file_history_manager.py` backup functionality, and LSP manager.
  - Reorganized test file naming for clarity (removed `_coverage` suffix from test files).

## 2.10.2 (March 15, 2026)

- **Fix: Ctrl+C Cancellation Propagation**:
  - Fixed issue where pressing Ctrl+C required multiple presses to cancel running tasks.
  - The `c-c` keybinding in `ui.py` now cancels `_running_llm_task` before calling `event.app.exit()`, matching the Escape key behavior.
  - Eliminates "Task was destroyed but it is pending!" errors when cancelling LLM operations.

- **Fix: Task Cancellation Cleanup**:
  - Added double-await pattern in `_process_messages_loop` to ensure cancelled tasks complete before continuing.
  - Re-raises `CancelledError` in `_stream_ai_response` and `_run_shell_command` for proper cancellation propagation.
  - Added explicit `stream.aclose()` in `run_agent.py` finally block to close async generators on cancellation.

- **Feature: Subagent Status Streaming**:
  - Added `stream_to_parent` method to `UIProtocol` interface for bypassing BufferedUI buffer during subagent execution.
  - Implemented `stream_to_parent` in `UI`, `StdUI`, and `BufferedUI` classes.
  - Updated `create_event_handler` in `stream_response.py` with `status_event` parameter for tool call/result notifications.
  - Subagent tool calls and results now display immediately in parent UI instead of waiting for task completion.

- **Fix: Duplicate Tool Call Display in Deferred Tool Flow**:
  - Fixed issue where tool call notifications (e.g., `🧰 call_xxx | DelegateToAgent...`) appeared twice in output when using deferred tool approvals.
  - Root cause: pydantic-ai fires `FunctionToolCallEvent` twice with identical `tool_call_id` - once when tool is deferred, once when executed.
  - Added `printed_tool_call_ids: set[str]` tracking in `create_event_handler()` to deduplicate prints.
  - Tool call/result events now use `status_fn` (bypasses buffer) for immediate visibility in subagent output.

## 2.10.1 (March 14, 2026)

- **Refactor: Streamlined Prompt System**:
  - Converted `mandate.md` and `journal_mandate.md` to concise table-based formats, reducing visual noise while preserving all rules.
  - Added explicit "Decision Flow" section to mandate with ordered delegation check, skill activation, and execution steps.
  - Added tier-aligned journal scope: Tier 1 skips journaling entirely, Tier 2 journals only on discoveries.
  - Condensed project context rules in `claude.py` from 25 lines to 10 lines with clear documentation hierarchy.

- **Refactor: Improved Delegate Tool Documentation**:
  - Unified terminology: `subagent` instead of `sub-agent` throughout tool docstrings.
  - Simplified docstring format with "USAGE" bullets pointing to mandate for delegation rules.
  - Reference to mandate Section 5 for "WHEN TO USE" guidance.

- **Refactor: Lazy Skill Manager Initialization**:
  - Removed `auto_load` parameter from `SkillManager.__init__`.
  - Added `_ensure_scanned()` method for lazy initialization on first access.
  - Reduces startup overhead when skills aren't immediately needed.

- **Refactor: Agent Naming**:
  - Renamed agent from `subagent` to `generalist` for clearer semantic meaning.
  - File renamed from `subagent.agent.md` to `generalist.agent.md`.

- **Fix: Persona Delegation Wording**:
  - Updated "Delegate only for exceptional scale" to "Delegate when context isolation is beneficial."
  - Corrects overly narrow guidance about when to delegate.

## 2.10.0 (March 12, 2026)

- **Feature: Grep Timeout Parameter**:
  - Added `timeout` parameter to `Grep` tool in `src/zrb/llm/tool/file.py`, allowing users to set a maximum execution time for search operations. This prevents long-running regex searches from blocking the agent indefinitely.

- **Feature: Parallel Agent Delegation**:
  - Enhanced `DelegateToAgent` tool in `src/zrb/llm/tool/delegate.py` to support parallel execution of multiple sub-agents, significantly improving performance for batch processing workflows.
  - Added `tool_factories` and `toolset_factories` support to `LLMTask`, enabling dynamic tool resolution at execution time.
  - Updated SubAgent system prompts and improved context handling for delegated tasks.

- **Refactor: Replace python-jose with PyJWT**:
  - Migrated JWT handling from `python-jose` to `PyJWT` in `src/zrb/runner/web_util/token.py` and `src/zrb/runner/web_util/user.py`.
  - PyJWT is a more focused, actively maintained library specifically for JWT operations.
  - Updated `pyproject.toml` dependency from `python-jose[cryptography]` to `PyJWT ^2.8.0`.

- **Refactor: Reduce Cyclomatic Complexity in Hook Matcher**:
  - Refactored `_evaluate_matchers` in `src/zrb/llm/hook/manager.py` from a 23-branch if/elif chain to a clean dispatch dictionary pattern.
  - Each matcher operator (EQUALS, NOT_EQUALS, CONTAINS, STARTS_WITH, ENDS_WITH, REGEX, GLOB) now has its own focused module-level function.
  - Improved maintainability: Adding new operators now simply requires extending the `_MATCHER_OPERATORS` dictionary.

- **Maintenance: Code Formatting and Test Coverage**:
  - Applied consistent code formatting across multiple files.
  - Added extensive test coverage for callbacks, commands, input handling, LLM agents, and delegate tools.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)

