🔖 [Documentation Home](../README.md)

## 2.19.1 (April 10, 2026)

- **Security: Dependency Vulnerability Patches**:
  - Updated `langchain-core` from `>=1.2.22` to `>=1.2.28` (CVE-2026-34070).
  - Added `cryptography >=46.0.7` requirement (CVE-2026-39892).
  - Maintained existing security pins: `pygments >=2.20.0`, `aiohttp >=3.13.4`, `pyasn1 >=0.6.3`.

- **Feature: Bash Tool Working Directory Support**:
  - Added `cwd` parameter to `run_shell_command()` for setting working directory.
  - Required for proper operation inside worktrees and different project directories.
  - Backward compatible: defaults to current directory if not specified.

- **Improvement: Code Analysis Tool**:
  - Changed `file_pattern` parameter default from `None` to empty string for consistency.
  - Added guidance for writing specific queries (e.g., "how is auth implemented?") vs vague ones.

- **Improvement: LSP Tools Parameter Handling**:
  - Fixed `symbol_kind` parameter handling in `find_definition()` to properly convert empty string to `None`.
  - Ensures compatibility with LSP manager expectations.

- **Maintenance: Dependency Updates**:
  - Updated `poetry.lock` with latest compatible versions.
  - Minor cleanup in LLM tool imports and parameter defaults.

## 2.19.0 (April 9, 2026)

- **Feature: Model Tiering and Transform Pipeline**:
  - New `custom_model_names` parameter on `LLMTask` and `LLMChatTask` for custom model name registration.
  - New `model_getter` callable: transforms model before UI display (e.g., show tier name instead of actual model).
  - New `model_renderer` callable: transforms model before API call (e.g., map tier name to actual model).
  - Enables advanced use cases: model tiering, cost optimization, fallback strategies.
  - Pipeline: base model → `model_getter` (active, shown in UI) → `model_renderer` (final for pydantic_ai).

- **Feature: Custom Model Autocomplete**:
  - `InputCompleter` now accepts `custom_model_names` for autocomplete suggestions.
  - Custom model names appear with highest priority in `/model` command completions.

- **Documentation: Model Tiering Example**:
  - New `examples/model-tiering/` directory with complete working example.
  - Demonstrates automatic model downgrading based on request count.
  - Shows tier schedule: requests 1-3 → pro, 4-6 → flash, 7+ → flash-lite.

- **Tests: New Coverage**:
  - `test/llm/task/test_llm_task.py`: Added tests for model getter/renderer pipeline (+130 lines).
  - `test/llm/task/test_llm_chat_task.py`: Added tests for `LLMChatTask` model params (+53 lines).
  - `test/llm/app/test_completion.py`: Added tests for custom model autocomplete (+28 lines).

## 2.18.1 (April 8, 2026)

- **Improvement: Journaling Hook Behavior**:
  - Journaling reminders now fire after every response instead of only at session end.
  - LLM now decides whether any content from the turn is worth noting.
  - Simplified hook state management and improved anti-recursion protection.
  - Journaling prompt now uses a configurable template (`journal_reminder.md`).

- **Feature: Robust Cross-platform Clipboard**:
  - Added native WSL support via PowerShell for reliable Windows clipboard access.
  - Enhanced Wayland support with multi-type MIME fallback (BMP, JPEG, TIFF) and auto-conversion to PNG.
  - Improved "missing tool" hints with environment-aware suggestions.

- **Improvement: LLM App Layout and UI**:
  - Refined layout and keybindings for the LLM application.
  - Improved `DefaultUI` and `MultiUI` event handling and response capture.
  - Slimmed down prompt definitions and improved template loading.

- **Tests: Coverage Expansion**:
  - New `test/runner/chat/test_chat_api.py` for comprehensive API testing.
  - New `test/llm/hook/test_matchers.py` and expanded hook processing tests.
  - Verified behavioral changes in journaling and clipboard logic.

## 2.18.0 (April 5, 2026)

- **Feature: Hook System SESSION_END Extensions**:
  - `HookResult.with_system_message()` now accepts `replace_response` parameter.
  - `replace_response=False` (default): Extended session runs for side effects, original response returned.
  - `replace_response=True`: Extended session's response replaces original.
  - Enables use cases like: journaling (side effects), summarization (replace response), transformation pipelines.
  - `HookExecutionResult` adds `replace_response` field for result processing.
  - New helper functions: `_extract_system_message()`, `_extract_replace_response()`, `_extract_additional_context()`.

- **Feature: Hook Factory Registration**:
  - New `HookManager.add_hook_factory()` method for dynamic hook registration.
  - Factories are called during hook loading to conditionally register hooks based on config.
  - Enables config-driven hook enabling/disabling without code changes.
  - Built-in journaling hook uses this pattern to respect `CFG.LLM_INCLUDE_JOURNAL`.

- **Feature: Built-in Journaling Hook**:
  - New `src/zrb/llm/hook/journal.py` with `JournalingHookHandler` class.
  - Tracks session activity via `POST_TOOL_USE` events.
  - Sends journal reminder at `SESSION_END` if session had meaningful activity.
  - Anti-recursion protection: only fires reminder once per session.
  - Auto-registered when `LLM_INCLUDE_JOURNAL=on`.

- **Refactoring: Hook Event Cleanup**:
  - Removed 5 unhandled events from `HookEvent` enum: `PERMISSION_REQUEST`, `SUBAGENT_START`, `SUBAGENT_STOP`, `TEAMMATE_IDLE`, `TASK_COMPLETED`.
  - Reduced from 14 events to 9 events (all now actually fired in code).
  - Updated `CLAUDE_EVENT_MATCHER_FIELDS` mapping in `manager.py`.
  - Updated documentation and examples to reflect actual events.

- **Bug Fix: SESSION_END Response Handling**:
  - Fixed bug where `original_output` was overwritten on each loop iteration in `run_agent.py`.
  - Now captures `_original_output` and `_original_history` only when session extension is triggered.
  - Ensures correct response returned whether using `replace_response=True` or `False`.

- **Improvement: Context Window Management**:
  - New `_filter_nil_content()` function filters None/nil content from messages.
  - Prevents "invalid message content type: <nil>" errors from OpenAI-compatible APIs.
  - New `_is_prompt_too_long_error()` helper detects context length errors.
  - New `_drop_oldest_turn()` function removes oldest conversation turn for context compaction.

- **Feature: Selective YOLO Mode**:
  - YOLO input now accepts comma-separated tool names for selective auto-approval.
  - Example: `--yolo "Write,Edit"` auto-approves only Write and Edit tools.
  - UI displays selective YOLO as `[Write,Edit]` in yellow.
  - Runtime command: `/yolo Write,Edit` to enable selective mode.
  - New `_parse_yolo_value()` function with full test coverage.

- **Feature: Bash Safe Command Policy**:
  - Auto-approves known-safe read-only commands (`ls`, `git status`, `cat`, `echo`, etc.).
  - Rejects commands with dangerous shell metacharacters (`>`, `|`, `;`, `&&`, `` ` ``, `$()`).
  - Conservative allowlist approach: only explicitly safe commands auto-approved.
  - Full test suite for policy validation (268 lines).

- **Bug Fix: Reserved Token Accounting**:
  - System prompt tokens now properly reserved in context window calculations.
  - Added `reserved_tokens` parameter to `run_agent()` and `fit_context_window()`.
  - Prevents context window overflow when system prompts are large.

- **Refactoring: Config Value Normalization**:
  - Standardized boolean config defaults: `"1"`/`"0"` → `"on"`/`"off"`.
  - Affects: `LOAD_BUILTIN`, `WEB_ENABLE_AUTH`, `HOOKS_ENABLED`, `HOOKS_DEBUG`, all `LLM_INCLUDE_*` flags.

- **Improvement: Prompt Documentation Slimming**:
  - `git_mandate.md`: Simplified from detailed tables to compact bullet lists.
  - `mandate.md`: Condensed sections, streamlined tool selection guidance.
  - Reduces token usage in prompts.

- **Improvement: Tool Docstring Simplification**:
  - Shortened docstrings across most LLM tools.
  - Removed verbose MANDATES sections, kept essential guidance.
  - Affected tools: `Bash`, `AnalyzeCode`, `LS`, `Glob`, `Read`, `ReadMany`, `Write`, `WriteMany`, `Edit`, `Grep`, `AnalyzeFile`, `WriteTodos`, `GetTodos`, `UpdateTodo`, `ClearTodos`, `OpenWebPage`, `SearchInternet`, `EnterWorktree`, `ExitWorktree`, `ListWorktrees`.

- **Documentation: Hooks Documentation**:
  - Expanded `docs/advanced-topics/hooks.md` with SESSION_END system messages section.
  - Added examples for both `replace_response=False` (side effects) and `replace_response=True` (transformation).
  - New `examples/llm-hooks/` directory with comprehensive hook examples.
  - Examples include: session tracking, permission control, journal reminder, response transformation.

- **Tests: New Coverage**:
  - `test/llm/hook/test_hook_result_processing.py`: Hook result extraction and journaling hook tests.
  - `test/llm/agent/test_run_agent.py`: Added `replace_response` functionality tests.
  - `test/llm/tool_call/tool_policy/test_bash_validation.py`: Comprehensive policy tests.
  - `test/llm/task/test_llm_chat_task.py`: Added `TestParseYoloValue` class.
  - Updated limiter tests for robustness (less brittle assertions).

## 2.17.0 (April 3, 2026)

- **Feature: Git Worktree Integration**:
  - New `Worktree` tools for isolated development: `EnterWorktree`, `ExitWorktree`, and `ListWorktrees`.
  - Enables safe experimentation and parallel work without affecting the main working tree.

- **Feature: Clipboard Utility**:
  - Added specialized clipboard handling in `src/zrb/llm/util/clipboard.py`.

- **Feature: Non-Persistent History**:
  - Added `NoSaveHistoryManager` for session-only history.

- **Feature: UI Improvements**:
  - Enhanced `BaseUI` and `DefaultUI` with more properties and better state management.

- **Improvement: Significant Test Coverage Expansion**:
  - Added extensive test suites for:
    - LSP tools (`test/llm/lsp/test_lsp_tools.py`)
    - Search tools (`test/llm/tool/search/test_search.py`)
    - Git Worktree (`test/llm/tool/test_worktree.py`)
    - JWT and Token management (`test/builtin/test_jwt.py`, `test/runner/web_util/test_token.py`)
    - Approval channels (`test/llm/approval/test_approval_channel.py`)
    - Rate limiting (`test/llm/config/test_limiter.py`)
    - Chat session management (`test/runner/chat/test_chat_session_manager.py`)

- **Improvement: LLM Tool Enhancements**:
  - Refactored `PlanTool`, `RagTool`, and `DelegateTool` for better reliability and error handling.
  - Improved search tool integration (Brave, Searxng, SerpApi).

- **Bug Fixes and Stability**:
  - Fixed agent execution logic in `src/zrb/llm/agent/run_agent.py`.
  - Safer command execution and string utility improvements.

## 2.16.0 (April 3, 2026)

- **Feature: Flexible Skill/Agent Search Configuration**:
  - New environment variables for configuring skill and agent search paths:
    - `ZRB_LLM_SEARCH_PROJECT` - Enable project directory traversal
    - `ZRB_LLM_SEARCH_HOME` - Search home directory (`~/.claude/`, `~/.zrb/`)
    - `ZRB_LLM_CONFIG_DIR_NAMES` - Config subdirectory names (`.claude:.zrb`)
    - `ZRB_LLM_BASE_SEARCH_DIRS` - Explicit base directories
    - `ZRB_LLM_EXTRA_SKILL_DIRS` / `ZRB_LLM_EXTRA_AGENT_DIRS` - Additional directories
    - `ZRB_LLM_PLUGIN_DIRS` - Plugin directories
  - Search priority: User Home → Project Traversal → Plugins → Base Dirs → Extra Dirs → Builtin
  - Enhanced `AgentManager` and `SkillManager` with flexible search capabilities.

- **Feature: Conversation Session Display**:
  - CLI now displays conversation name at the end of LLM chat task execution.
  - Session name retrieved from `__conversation_name__` in shared context XCom.

- **Enhancement: Env Class Properties**:
  - Added `name`, `default`, `auto_render`, `link_to_os`, `os_name` properties to `Env` class.

- **Enhancement: BaseUI Command Properties**:
  - Added properties: `assistant_name`, `initial_message`, `exit_commands`, `info_commands`, `save_commands`, `load_commands`, `attach_commands`, `redirect_output_commands`, `yolo_toggle_commands`, `set_model_commands`, `exec_commands`, `custom_commands`, `summarize_commands`.

- **Bug Fix: Command Handling**:
  - Fixed `/compress` and `/compact` commands.
  - Fixed test for hook manager.

- **Improvement: Testing**:
  - Removed private functions from coverage requirements.
  - Updated pytest configuration.

- **Security: Dependency Updates**:
  - Upgraded dependencies due to security concerns.

- **Code Quality**:
  - Safer `git branch prune` operation with better validation.
  - Better naming conventions across LLM modules.
  - Code formatting improvements.

## 2.15.1 (April 2, 2026)

- **Enhancement: New Skills for Development Workflow**:
  - `debug` skill: Systematic diagnosis for build failures and behavioral issues.
  - `refactor` skill: Safe structural refactoring preserving behavior.
  - `testing` skill: Comprehensive TDD workflow (RED→GREEN→REFACTOR).
  - Deprecated `quality-assurance` skill (replaced by specialized skills).

- **Enhancement: Improved init Skill**:
  - Now generates universal `AGENTS.md` (works with any LLM: Claude, Gemini, GPT).
  - Systematic codebase analysis with exact command extraction.
  - Convention extraction from actual code patterns.

- **Enhancement: New Agents**:
  - `code-reviewer.agent.md`: Read-only code review specialist with severity-rated findings.
  - `researcher.agent.md`: Web and codebase research agent for deep investigation.

- **Improvement: Prompt Documentation**:
  - `mandate.md`: Added Scope Discipline, Verification, Security, and Confirmation sections.
  - `persona.md`: Simplified to essentials.
  - `journal_mandate.md`: Added tiered protocol (Tier 1 direct write, Tier 2 full protocol).

- **Improvement: Tool Docstrings**:
  - Enhanced documentation for `Bash`, `Write`, `WriteMany`, `Edit` tools.
  - Clearer mandates for file operations and command execution.

- **Improvement: review Skill**:
  - Added OWASP Top 10 security checklist integration.
  - Severity ratings (CRITICAL → HIGH → MEDIUM → LOW → INFO).
  - Structured output format with findings and verdicts.

- **Improvement: core-coding Skill**:
  - Integration signals for `testing`, `debug`, `refactor`, and `review` skills.
  - Test-First workflow guidance for new behavior.

## 2.15.0 (April 1, 2026)

- **Feature: HTTP Chat API**:
  - New `/api/v1/chat/` endpoints for programmatic chat access.
  - `GET /api/v1/chat/sessions` - List chat sessions with pagination.
  - `POST /api/v1/chat/sessions` - Create new session.
  - `DELETE /api/v1/chat/sessions/{session_id}` - Delete session.
  - `GET /api/v1/chat/sessions/{session_id}/messages` - Get session messages.
  - `POST /api/v1/chat/sessions/{session_id}/messages` - Send message to session.
  - `GET /api/v1/chat/sessions/{session_id}/stream` - SSE stream for real-time responses.
  - `GET /api/v1/chat/sessions/{session_id}/history` - Get conversation history.
  - `DELETE /api/v1/chat/sessions/{session_id}/history` - Clear session history.
  - `GET /api/v1/chat/sessions/{session_id}/yolo` - Get YOLO mode status.
  - `POST /api/v1/chat/sessions/{session_id}/yolo` - Toggle YOLO mode.
  - Requires web auth configuration.

- **Feature: Chat Session Management**:
  - `ChatSessionManager` provides persistent session storage with SQLite.
  - Sessions store: session_id, session_name, created_at, updated_at.
  - Messages stored with: role, content, tool_calls, timestamp.
  - Page/limit pagination support for session and message listing.

- **Feature: Web Chat UI**:
  - New `/chat/` web route with full interactive chat interface.
  - Modern JavaScript-based UI with real-time streaming.
  - Session management (create, delete, switch).
  - Message history with tool call visualization.
  - YOLO mode toggle.
  - Styled with CSS for responsive design.

- **Feature: Stream Response Handling**:
  - Improved `StreamResponseHandler` in `src/zrb/llm/util/stream_response.py`.
  - Better handling of tool calls during streaming.
  - Proper message part accumulation for complex responses.

- **Refactoring: UI Module Cleanup**:
  - Removed unused `is_model_auto_stop` parameter from multiple UI classes.
  - Simplified `BaseUI`, `SimpleUI`, `DefaultUI`, `StdUI` constructors.
  - Deprecated unused `input_queue` property in favor of `handle_incoming_message()`.

- **Refactoring: LLM Task Improvements**:
  - `LLMChatTask` and `LLMTask` now support `None` values for optional parameters.
  - Better default handling for `timeout` and `model` parameters.
  - Removed deprecated `llm_task_core` parameter from various methods.

- **Bug Fix: Delegate Tool Error Handling**:
  - Fixed `DelegateTool` to properly return error messages instead of raising exceptions.

- **Documentation: LLM Custom UI Guide**:
  - Updated `docs/advanced-topics/llm-custom-ui.md` with new patterns and examples.

- **Tests: Comprehensive Coverage**:
  - New `test/runner/chat/` test suite for HTTP Chat API.
  - New `test/llm/ui/` test suite for SimpleUI and MultiUI.
  - Enhanced existing UI and agent tests.



## 2.14.2 (March 29, 2026)

- **Bug Fix: Type Annotation Correction**:
  - Fixed `dict[str, any]` → `dict[str, Any]` in `chat_tool_policy.py`.
  - Added missing `from typing import Any` import.

- **Code Cleanup**:
  - Removed unused `import sys` from `terminal_approval_channel.py`.

- **Security: Dependency Updates**:
  - Pinned `cryptography = "^46.0.6"` to address CVE-2026-34073 (transitive dependency via PyJWT).
  - Updated `langchain-core >= 1.2.22` constraint for CVE-2026-34070.

## 2.14.1 (March 28, 2026)

- **Enhancement: Improved LLM Prompt Guidelines**:
  - `journal_mandate.md`: Restructured journaling triggers with clearer examples and conditions.
  - Added mandatory `core-journaling` skill activation before writing journal entries.
  - `mandate.md`: Added "Software Engineering" section requiring `core-coding` skill activation for coding tasks.
  - `persona.md`: Simplified response style guidance for better clarity.

## 2.14.0 (March 28, 2026)

- **Feature: MultiUI for Dual-Channel Support**:
  - New `MultiUI` class in `zrb.llm.ui.multi_ui` broadcasts output to all channels and waits for first input response.
  - Enables running CLI alongside external channels (Telegram, SSE) simultaneously.
  - `LLMChatTask` supports multiple UIs via new `append_ui()` and `append_ui_factory()` methods.
  - `run_agent()` accepts `list[UIProtocol]` for the `ui` parameter, auto-creating `MultiUI` when needed.

- **Feature: MultiplexApprovalChannel**:
  - New `MultiplexApprovalChannel` broadcasts approval requests to multiple channels.
  - First response wins and cancels pending requests on other channels.
  - `LLMChatTask` supports multiple approval channels via `append_approval_channel()`.
  - Automatic `MultiplexApprovalChannel` creation when using `append_approval_channel()`.

- **Architecture: Module Reorganization**:
  - UI classes moved from `src/zrb/llm/app/` to `src/zrb/llm/ui/`.
  - Approval channel classes split into dedicated modules:
    - `approval_channel.py` - Protocol and dataclasses
    - `terminal_approval_channel.py` - Terminal implementation
    - `null_approval_channel.py` - Auto-approve implementation
    - `multiplex_approval_channel.py` - Multi-channel combiner
  - Import paths updated: `zrb.llm.ui` replaces `zrb.llm.app`.

- **Feature: LLMChatTask Enhanced API**:
  - `set_ui()` now accepts single `UIProtocol` or `list[UIProtocol]`.
  - `append_ui()` adds a UI to the existing list.
  - `append_ui_factory()` adds a UI factory to the existing list.
  - `append_approval_channel()` adds an approval channel to the existing list.
  - New `_print_conversation_name()` helper for session display.

- **Bug Fix: History Manager Content Sanitization**:
  - Improved `_clean_corrupted_content()` in `FileHistoryManager` with strict field filtering.
  - Properly handles `tool-call`, `tool-return`, `text`, `system-prompt`, `thinking`, `retry-prompt` part kinds.
  - Removes `None` values and reconstructs minimal valid part dictionaries.

- **Refactoring: run_agent Improvements**:
  - Added debug logging for tool confirmation and approval channel resolution.
  - Automatic `TerminalApprovalChannel` wrapping when external approval channel is provided.
  - Better handling of single UI vs. list of UIs.

- **Security: Dependency Updates**:
  - Updated `requests` to `^2.33.0`.
  - Added `langchain-core >= 1.2.22` as optional dependency for `voyageai` extra (CVE-2026-34070).

- **Examples: Simplified Structure**:
  - Removed `examples/chat-telegram-cli/` - dual-channel pattern now integrated into `chat-telegram/`.
  - Updated `chat-telegram/` demonstrates `append_ui_factory()` and `append_approval_channel()` usage.
  - Updated `chat-sse/` uses simplified dual-mode API.

- **Tests: Increased Coverage**:
  - New `test/llm/approval/test_approval_channel.py` for `MultiplexApprovalChannel`, `TerminalApprovalChannel`, `NullApprovalChannel`.
  - New `test/llm/custom_command/test_skill_command_factory.py`.
  - Enhanced `test/llm/app/test_ui.py` with `MultiUI` tests.
  - New `test/runner/web_util/test_cookie.py`.

## 2.13.0 (March 24, 2026)

- **Breaking Change: SimpleUI Constructor API**:
  - `SimpleUI.__init__` now requires `ctx`, `llm_task`, and `history_manager` parameters (previously optional).
  - `EventDrivenUI.__init__` and `PollingUI.__init__` updated with explicit parameter signatures.
  - Use `create_ui_factory(MyUI)` for simplified registration without manual constructor handling.
  - Updated documentation with clearer constructor parameter descriptions.

- **Feature: handle_incoming_message() Method**:
  - Added to `EventDrivenUI` and `PollingUI` for proper message routing.
  - Solves the common pitfall where `input_queue.put()` loses messages when LLM is idle.
  - Routes correctly: unblocks `get_input()` when LLM waiting, or starts new turn when idle.
  - `_waiting_for_input` flag tracks LLM state for intelligent routing.

- **Feature: SSE Chat Example**:
  - Added `examples/chat-sse/` demonstrating Server-Sent Events for real-time LLM chat.
  - Shows proper `handle_incoming_message()` integration pattern.
  - Includes HTTP endpoints: `POST /chat`, `GET /stream`, `GET /status`, `GET /history`.
  - Automatic keepalive prevents timeout, no polling needed.

- **Refactoring: PollingUI Internal API**:
  - `input_queue` → `_input_queue` (internal) with `input_queue` property for backward compatibility.
  - Public property deprecated in favor of `handle_incoming_message()` for proper routing.

- **Examples Removal**:
  - Removed `chat-discord`, `chat-whatsapp`, `chat-http-api`, `chat-websocket` examples.
  - SSE example provides clearer pattern for HTTP-based integrations.

- **Documentation: Mental Model Overhaul**:
  - Added comprehensive architecture diagrams to `docs/advanced-topics/llm-custom-ui.md`.
  - Method mapping tables show `BaseUI → SimpleUI` translation.
  - Clear "What Each Level Abstracts Away" table for choosing base class.
  - Fixed ASCII diagram alignment in `base_ui.py` comments.

## 2.12.1 (March 23, 2026)

- **Bug Fix: Graceful Shutdown Handling**:
  - Fixed `KeyboardInterrupt` handling in `log_session_state()` (`src/zrb/task/base/lifecycle.py`).
  - Added defensive try/except blocks to prevent crashes when context is unavailable during shutdown.
  - Added `KeyboardInterrupt` to exception handlers alongside `asyncio.CancelledError`.

- **Bug Fix: Telegram Multiplexer Shutdown**:
  - Improved shutdown handling in `examples/chat-telegram-cli/zrb_init.py`.
  - Added `asyncio.timeout` for graceful shutdown (1s updater stop, 0.5s app stop/shutdown).
  - Added `is_shutdown_requested()` checks to prevent operations during shutdown.
  - Installed asyncio signal handler for graceful SIGINT handling.
  - Fixed cleanup race conditions with `asyncio.Lock` and `_cleanup_done` flag.
  - Force exit with `os._exit(0)` to bypass long executor thread waits.
  - Approval channels now return `approved=False` during shutdown.

- **Documentation: ASCII Diagram Formatting**:
  - Fixed ASCII box diagram alignment across 11+ README files.
  - Consistent box widths, aligned vertical edges, centered text.
  - Updated examples: chat-discord, chat-http-api, chat-minimal-ui, chat-telegram-cli, chat-websocket, chat-whatsapp, web-auth, task-dependencies, trigger-scheduler.

- **Examples: File Renaming**:
  - Renamed `chat-http-api/zrb_init.py` → `main.py`.
  - Renamed `chat-websocket/zrb_init.py` → `main.py`.
  - Updated README references to use `python main.py` instead of `python zrb_init.py`.

- **Dependency Update**:
  - Updated `pydantic-ai-slim` from 1.67.0 to 1.70.0.

## 2.12.0 (March 23, 2026)

- **Feature: Simplified UI Extension API**:
  - Added `zrb.llm.app.simple_ui` module with `SimpleUI`, `EventDrivenUI`, and `PollingUI` base classes.
  - `SimpleUI`: Implement just 2 methods (`print()`, `get_input()`) for basic backends (CLI, file-based).
  - `EventDrivenUI`: Implement `print()` and `start_event_loop()` for event-driven backends (Telegram, Discord, WhatsApp).
  - `PollingUI`: Implement `print()` with built-in queues for polling backends (HTTP API, WebSocket).
  - `create_ui_factory()` helper reduces boilerplate from 20+ lines to 1 line.
  - `UIConfig` dataclass consolidates 25+ configuration parameters into a single object.

- **Feature: BufferedOutputMixin**:
  - New mixin for rate-limited backends (Telegram, Discord) that need to batch output.
  - Prevents fragmented messages when LLM streams tokens.
  - Configurable `flush_interval` and `max_buffer_size`.

- **Feature: Enhanced BaseUI**:
  - Added default implementations for `ask_user()` and `run_async()` in `BaseUI`.
  - `_message_queue` and `_process_messages_loop()` now handle the full chat loop.
  - Better separation between UI concerns (output, input, commands, session).

- **Examples: New UI Implementations**:
  - Added `examples/chat-minimal-ui/` - Minimal SimpleUI example (~40 lines).
  - Added `examples/chat-telegram/` - Telegram bot using EventDrivenUI + BufferedOutputMixin.
  - Added `examples/chat-telegram-cli/` - Multiplexed UI (CLI + Telegram) with dual-channel approval.
  - Added `examples/chat-discord/` - Discord bot using EventDrivenUI.
  - Added `examples/chat-whatsapp/` - WhatsApp Business bot using EventDrivenUI.
  - Added `examples/chat-http-api/` - HTTP polling API using PollingUI.
  - Added `examples/chat-websocket/` - WebSocket server using PollingUI.
  - All examples renamed from `examples/telegram/` pattern to `examples/chat-*/` for consistency.

- **Documentation: Comprehensive UI Extension Guide**:
  - Merged `docs/extension-guide.md` into `docs/advanced-topics/llm-custom-ui.md`.
  - Progressive complexity: SimpleUI → EventDrivenUI → PollingUI → BaseUI.
  - Working examples for each pattern.
  - Migration guide from `BaseUI` to `SimpleUI` (78% code reduction).
  - Pattern comparison table for choosing the right base class.

## 2.11.0 (March 21, 2026)

- **Feature: Multi-Channel Approval System**:
  - Added `zrb.llm.approval` module with `ApprovalChannel` protocol for routing tool call approvals through different channels (Terminal, Telegram, Web, etc.).
  - `ApprovalContext` and `ApprovalResult` dataclasses provide structured approval metadata.
  - `TerminalApprovalChannel` wraps existing UI patterns for backward compatibility.
  - `NullApprovalChannel` enables automatic approval for YOLO mode.
  - `current_approval_channel` context variable propagates approval channel to nested agents.

- **Feature: Extensible BaseUI for Custom LLM Interfaces**:
  - Extracted `BaseUI` class from `UI` into `src/zrb/llm/app/base_ui.py`.
  - `BaseUI` provides the full interactive chat loop (command parsing, message queue, session management, tools) while allowing I/O customization.
  - Enables creating custom UI implementations (Telegram, Web, Multiplexed) without reimplementing LLM interaction logic.
  - Key methods: `_submit_user_message()`, `_process_messages_loop()`, `_stream_ai_response()`.

- **Feature: UI Factory Support for LLMChatTask**:
  - Added `ui` and `ui_factory` parameters to `LLMChatTask` for programmatic UI injection.
  - `set_ui()` method allows setting a custom `UIProtocol` instance.
  - `set_ui_factory()` method allows dynamic UI creation with access to context and task parameters.
  - Factory signature: `(ctx, llm_task_core, history_manager, ui_commands, initial_message, initial_conversation_name, initial_yolo, initial_attachments) -> UIProtocol`.

- **Feature: Approval Channel Injection**:
  - Added `approval_channel` parameter to `LLMTask` and `LLMChatTask`.
  - `set_approval_channel()` method on `LLMChatTask` for runtime configuration.
  - Enables multi-channel approval (e.g., both Telegram and Terminal receive approval requests simultaneously).

- **Examples: Custom UI Implementations**:
  - Added `examples/telegram/` demonstrating single-channel Telegram UI extending `BaseUI`.
  - Added `examples/telegram-cli/` demonstrating multiplexed UI with both Telegram and CLI simultaneously.
  - Multiplexer architecture: single shared message queue, multiple I/O channels, first-response-wins for approvals.
  - Documentation added in `docs/advanced-topics/llm-custom-ui.md`.

- **Tests: Approval Channel Coverage**:
  - Added `test/llm/approval/test_approval_channel.py` with comprehensive tests for `ApprovalChannel` protocol, `ApprovalContext`, `ApprovalResult`, and channel implementations.
  - Added `test/llm/task/test_llm_chat_task.py` for UI factory and approval channel integration.



## 2.10.4 (March 19, 2026)

- **Fix: WriteMany Tool Permission Check**:
  - Fixed `chat_tool_policy.py` to properly validate paths for `WriteMany` tool calls.
  - The permission check now inspects the `files` parameter (list of dicts with `path` key) in addition to `path` and `paths`.
  - Previously, WriteMany calls to journal directories would fail auto-approval because only `path`/`paths` were checked.

- **Fix: Event Loop Closure During Shutdown**:
  - Fixed `RuntimeError` exceptions when the UI event loop closes during shutdown.
  - All `asyncio.sleep()` calls in `_scroll_output_loop`, `_process_messages_loop`, and `_trigger_loop` now catch `RuntimeError` and break cleanly.
  - Prevents "Event loop is closed" errors when exiting the application.

- **Refactor: Remove Unused Imports**:
  - Removed unused `warnings` and `AsyncExitStack` imports from `llm_chat_task.py`.

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


## 2.9.2 (March 10, 2026)

- **Fix: Strengthen LLM System Prompt Mandates**:
  - **journal_mandate.md**: Added explicit "When to Write (Examples)" section with concrete triggers (user preferences, decisions, errors, session insights) and clear "Do NOT write for trivial queries" prohibition. This fixes regression from 2.7.x where the condensed version lost actionable examples.
  - **git_mandate.md**: Added explicit list of state-changing commands requiring approval and more read-only commands. Changed protocol from `git add <files>` to generic `git <command> <args>` pattern.

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


## 2.6.24 (March 3, 2026)

- **Fix: LLM Tool API Breakage & Mandate Improvements**:
  - **API Breakage Resolution**: Fixed `analyze_file` API breakage by adding `auto_truncate: bool = True` parameter. The function was calling `read_file()` without the required `auto_truncate` parameter after recent file tool simplifications. Maintains backward compatibility with sensible default.
  - **Tool Mandate Rewrite**: Rewrote tool mandates in `src/zrb/llm/tool/file.py` and `src/zrb/llm/tool/code.py` to provide LLM usage guidance instead of implementation details. Mandates now focus on when/how to use tools (general exploration, targeted discovery, etc.) rather than describing internal implementation. Mandates are included in prompts via pydantic-ai and should guide LLM usage.
  - **Flexible Exclusion Control**: Added `exclude_patterns` parameter to `list_files`, `glob_files`, `search_files`, and `analyze_code` functions. Users can pass `[]` to include all files or custom patterns to override default exclusions. Maintains `DEFAULT_EXCLUDED_PATTERNS` as sensible default while providing flexibility for `.venv` and other directory inclusion.
  - **Enhanced Git Mandate**: Updated `src/zrb/llm/prompt/markdown/git_mandate.md` with assertive language to prevent violations. Added 🚨 visual alert, explicitly calls out `git add` as "STAGING - this is a state change!", clarifies "EACH operation requires SEPARATE approval", and provides concrete examples of what doesn't count as approval ("Stage files" ≠ permission to commit, "Update code" ≠ permission to stage).

- **Test Verification**:
  - **Comprehensive Test Suite**: All 37 tool-related tests pass with updated architecture.
  - **Backward Compatibility**: All changes maintain backward compatibility with sensible defaults (`auto_truncate=True`, `exclude_patterns=None` defaults to `DEFAULT_EXCLUDED_PATTERNS`).

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.24 in `pyproject.toml`.

## 2.6.23 (March 2, 2026)

- **Fix: Missing `_remove_lines_from_middle` Function in Truncation Algorithm**:
  - **Bug Resolution**: Added the missing `_remove_lines_from_middle()` function to `src/zrb/util/truncate.py` that was being called at line 91 but never defined. The function properly removes lines from the middle section when content exceeds head+tail line limits.
  - **Truncation Algorithm Completion**: The multi-stage truncation algorithm now has all required helper functions: `_remove_lines_from_middle`, `_remove_lines_from_tail`, and `_remove_lines_from_head` for complete head-tail preservation logic.
  - **Test Verification**: Verified the fix works correctly with test cases showing proper head lines, truncation message, and tail lines in output.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.23 in `pyproject.toml`.

## 2.6.22 (March 2, 2026)

- **Documentation Enhancement: Summarization Logic Documentation**:
  - **Cost-Benefit Optimization**: Added documentation explaining that summarization is skipped if tokens are within threshold AND the portion to summarize is less than 30% of the conversational token threshold. Prevents unnecessary summarization when little context would be saved.
  - **Configuration Clarity**: Updated configuration section with default values (60% of max context window for conversational threshold, 50% of conversational threshold for message threshold, 100 for summary window) and clarified that environment variables are accessed in code via `CFG.LLM_*` properties.
  - **Constants Documentation**: Added section documenting `SUMMARY_PREFIX` and `TRUNCATED_PREFIX` constants used in the summarization system.
  - **Message Conversion Details**: Added section explaining how different message parts (ImageUrl, BinaryContent, AudioUrl, ToolCallPart, ToolReturnPart) are converted to text representations for summarization.
  - **Safety Mechanisms**: Documented safety mechanisms including safe copy for mutable content, tool response skipping for ToolDenied/ToolApproved messages, depth limiting (max 5), and backward compatibility support.

- **Improvement: Ollama Model Auto-Completion**:
  - **Ollama Integration**: Added Ollama model auto-completion to zrb UI, enabling users to select from locally available Ollama models.
  - **Dynamic Model Fetching**: Created `_get_ollama_models()` method that dynamically fetches available models via `ollama ls` command with 30-second caching to avoid repeated shell calls.
  - **Pydantic-AI Compatibility**: Models are formatted as `ollama:<model-name>` for seamless compatibility with pydantic-ai's Ollama integration.

- **Improvement: PromptManager Enhancement**:
  - **Property Accessors**: Added property getters and setters for `include_persona`, `include_mandate`, `include_git_mandate`, `include_system_context`, `include_journal`, `include_claude_skills`, and `include_cli_skills` to enable dynamic configuration of prompt components.

- **Improvement: Tool Docstring MANDATES Enhancement**:
  - **Bash Tool**: Enhanced with timeout guidance (default 30s, max 10min), truncation notice, and batch command optimization tips.
  - **AnalyzeCode Tool**: Clarified as LLM sub-agent with resource-intensity warnings and guidance for single file vs directory analysis.
  - **File Tools Comprehensive MANDATES**: Added detailed MANDATES sections to all file tools:
    - **LS**: Depth limiting, excluded patterns, truncation controls, Glob preference guidance.
    - **Glob**: Pattern syntax, result truncation, LS alternative guidance.
    - **Read**: Line range selection, pagination, truncation limits, ReadMany preference.
    - **ReadMany**: Error handling, batch processing, efficiency guidance.
    - **Write**: Directory creation, mode usage, Edit preference, verification steps.
    - **WriteMany**: File dict format, mode defaults, batch efficiency.
    - **Edit**: Context verification, count parameter, error handling, Write alternative.
    - **Grep**: Python regex syntax, file_pattern restrictions, truncation, alternative tools.
    - **AnalyzeFile**: Resource intensity, truncation, Read/AnalyzeCode alternatives.
  - **Web Tools MANDATES**: Enhanced OpenWebPage with summarization behavior and links documentation; enhanced SearchInternet with API key requirements, pagination, and configuration options.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.22 in `pyproject.toml`.

## 2.6.21 (February 28, 2026)

- **Improvement: Skill Naming Convention Standardization**:
  - **Snake Case to Kebab Case Migration**: Standardized all skill names from snake_case to kebab-case format for consistency across the system: `core_coding` → `core-coding`, `core_journaling` → `core-journaling`, `git_summary` → `git-summary`, `quality_assurance` → `quality-assurance`, `research_and_plan` → `research-and-plan`.
  - **Directory Structure Updates**: Updated skill directory names to match new kebab-case naming convention, ensuring file system consistency with skill activation references.
  - **Cross-Reference Updates**: Updated all references to skill names in mandate files (`mandate.md`, `journal_mandate.md`), agent definitions (`subagent.agent.md`), and skill creator documentation to reflect new naming convention.

- **Improvement: Skill Activation Tool Enhancement**:
  - **RELOAD REQUIRED Directive**: Added explicit guidance to `ActivateSkill` tool description in `src/zrb/llm/tool/skill.py` noting that long conversations with history summarization may cause skill instruction details to be forgotten, requiring tool re-invocation to reload instructions into context.
  - **Proactive Skill Management**: Enhanced tool documentation to encourage proactive skill reloading when users feel they have lost exact details of an active skill, improving reliability of skill-based workflows.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.21 in `pyproject.toml`.

## 2.6.20 (February 28, 2026)

- **Improvement: Enhanced Truncation Algorithm with Character Limit Support**:
  - **Multi-Stage Truncation Algorithm**: Enhanced `truncate_output` function in `src/zrb/util/truncate.py` with comprehensive character limit support following a multi-stage algorithm: (1) If content ≤ max_chars, return as-is; (2) Apply max_line_length truncation to all lines first; (3) If still > max_chars and line count > head_lines + tail_lines, remove lines from middle; (4) If still > max_chars, remove lines from tail (from top of tail section); (5) If still > max_chars, remove lines from head (from bottom of head section); (6) Insert truncation message only at end at location of removed lines.
  - **Character Truncation as Last Resort**: Added character-level truncation as final fallback with proper size accounting (available_for_content = max_chars - message_size) and edge case handling for very small max_chars (<15) returning minimal "..." indicator.
  - **Accurate Truncation Metadata**: Enhanced function to return tuple `(truncated_string, TruncationInfo)` with accurate truncation metrics (original/truncated lines/chars, omitted lines/chars, truncation_type) for precise truncation notices in tool outputs.
  - **Refactored for Maintainability**: Broke down 200+ line monolithic function into 7 focused helper functions (`_truncate_line`, `_apply_line_length_truncation`, `_remove_lines_from_middle`, `_remove_lines_from_tail`, `_remove_lines_from_head`, `_build_result_with_truncation_message`, `_apply_character_truncation`) while preserving exact algorithm and public API.

- **Improvement: Web Authentication Configuration Standardization**:
  - **Environment Variable Consistency**: Standardized web authentication environment variables: `ZRB_WEB_SECRET` → `ZRB_WEB_SECRET_KEY`, `ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES` → `ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`, `ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES` → `ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES`.
  - **Configuration Property Updates**: Updated `Config` class properties and setters in `src/zrb/config/config.py` to match new environment variable names while maintaining backward compatibility through proper environment variable mapping.
  - **Documentation Updates**: Updated configuration documentation in `docs/installation-and-configuration/configuration/README.md`, `docs/installation-and-configuration/configuration/llm-integration.md`, and `docs/installation-and-configuration/configuration/web-auth-config.md` to reflect new variable names and provide clearer guidance.

- **Improvement: Enhanced Prompt Customization Hierarchy**:
  - **Multi-Level Prompt Override System**: Enhanced prompt loading in `src/zrb/llm/prompt/prompt.py` with four-level hierarchy: (1) `ZRB_LLM_PROMPT_DIR` (highest priority), (2) Environment variable direct override (`ZRB_LLM_PROMPT_{name}`), (3) `ZRB_LLM_BASE_PROMPT_DIR` (organization-wide), (4) Package default (lowest priority).
  - **New Configuration Option**: Added `ZRB_LLM_BASE_PROMPT_DIR` environment variable and `Config.LLM_BASE_PROMPT_DIR` property for organization-wide prompt overrides that apply across multiple projects.
  - **Documentation Enhancement**: Updated LLM integration documentation with clear search order explanation and examples for multi-level prompt customization.

- **Improvement: Core Mandate & Skill System Refinements**:
  - **Mandate Restructuring**: Reorganized `mandate.md` with clearer Universal Principles (Structured Thinking, Context-First, No Destructive Assumptions) and Absolute Directives focusing on secret protection and self-correction.
  - **Git Mandate Strengthening**: Enhanced `git_mandate.md` with "ABSOLUTE RULES" format, explicit prohibition examples, and strict approval protocol emphasizing "Assist, don't autonomously manage git."
  - **Skill System Consolidation**: Consolidated and renamed skills for better clarity: `core_journal` → `core_journaling`, `test` → `quality_assurance`, `research` → `research_and_plan`, `debug` → integrated into `quality_assurance`, removed redundant skills (`commit`, `core_mandate_brownfield`, `core_mandate_documentation`, `plan`, `pr`).
  - **Agent Simplification**: Consolidated multiple specialized agents into single `subagent.agent.md` for general delegation tasks, removing `coder.agent.md`, `explorer.agent.md`, `planner.agent.md`, `researcher.agent.md`, `reviewer.agent.md`.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.20 in `pyproject.toml`.
  - **Test Updates**: Updated `test/config/test_config.py` to reflect new environment variable names for web authentication configuration.

## 2.6.19 (February 27, 2026)

- **Improvement: Reusable Truncation Logic**:
  - **Centralized Logic**: Extracted line-length limit and head/tail preservation logic into `truncate_output` in `src/zrb/util/truncate.py`.
  - **Tool Consolidation**: Refactored `Grep`, `Read`, and `Bash` tools to import and use this shared utility, ensuring consistent and robust output truncation across the system.

- **Fix: Unbounded Line Lengths in Tool Outputs**:
  - **Grep Tool Truncation**: Addressed issue where matching against massive single-line files (e.g., minified JS or JSON dumps) would return megabytes of data. `_get_file_matches` in `src/zrb/llm/tool/file.py` now enforces a 1,000-character limit per line.
  - **Bash Tool Truncation**: Similarly updated `src/zrb/llm/tool/bash.py` to prevent giant single-line outputs from bloating the history.
  - **Read Tool Truncation**: Updated `read_file` to ensure individual lines are safely truncated when returning specific file line ranges.

- **Fix: Tool Execution Rejection Reason Truncation**:
  - **Preserved User Context**: Removed the hardcoded 500-character truncation limit for user rejection reasons in `src/zrb/llm/tool_call/handler.py`. Detailed feedback and code snippets provided during tool execution rejection are now passed to the AI exactly as is.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.19 in `pyproject.toml`.

## 2.6.18 (February 27, 2026)

- **Optimization: System Prompt Token Efficiency & Directive Strength**:
  - **Comprehensive Prompt Optimization**: Reduced system prompt from ~7K to ~5.8K tokens (17% overall reduction) while maintaining all critical directives and enforcement strength.
  - **Mandate.md Optimization**: Reduced from ~1,500 to ~800 tokens (47% reduction) by removing redundancies, tightening language, and eliminating filler while preserving Brownfield Protocol, Execution Framework, and safety directives.
  - **Persona.md Optimization**: Reduced from ~300 to ~200 tokens (33% reduction) with concise phrasing while maintaining "Brownfield Specialist" and "Pragmatic Doer" core identity.
  - **Journal Mandate Optimization**: Reduced from ~500 to ~350 tokens (30% reduction) by removing redundant phrasing and tightening "When to Read/Update" sections while keeping critical timing rules.
  - **Git Mandate Optimization**: Reduced from ~400 to ~280 tokens (30% reduction) by shortening verbose operation lists and consolidating "Core Principles" with tighter phrasing.
  - **Brownfield Protocol Analysis**: Documented AI's "knowing-doing gap" violation of mandate 2.2 (not activating core_mandate_brownfield before codebase work) and strengthened enforcement language.

- **Improvement: Token Estimation Accuracy**:
  - **Char-to-Token Ratio Correction**: Updated fallback token estimation from `char // 3` to `char // 4` in `LLMLimiter._count_tokens()` for more accurate token counting when tiktoken is not available.
  - **Truncation Logic Update**: Changed `truncate_text()` fallback from `max_tokens * 3` to `max_tokens * 4` to match the improved character-to-token ratio.
  - **Test Updates**: Updated test expectations in `test_limiter_coverage.py` and `test_limiter_explosion.py` to reflect the more accurate token estimation.

- **Improvement: Sequential Execution Enforcement**:
  - **Strategic Tool Selection**: Emphasized surgical tool usage with conservative limits and scopes for better context efficiency.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.18 in `pyproject.toml`.

## 2.6.17 (February 26, 2026)

- **Fix: Summarizer Brittle String Prefix Detection & Tool Denial Leakage**:
  - **Robust Type-Based Detection**: Replaced brittle string prefix checking in `src/zrb/llm/summarizer/message_processor.py` with type-based detection using `isinstance(safe_content, (ToolDenied, ToolApproved))` from pydantic_ai. This prevents summarization failures when tool denial/approval message wording changes.
  - **Module-Level Constants**: Added `SUMMARY_PREFIX = "SUMMARY OF TOOL RESULT:"` and `TRUNCATED_PREFIX = "TRUNCATED TOOL RESULT:"` as module-level constants, eliminating hardcoded string matching and ensuring consistent prefix usage across generation and detection.
  - **Tool Denial Message Handling**: Enhanced summarizer to skip processing for tool denial/approval messages, preventing wasted processing time on non-tool-result content.
  - **Uppercase Prefix Standardization**: Updated all prefix strings to uppercase format for consistency and clarity.

- **Fix: Tool Confirmation Output Leakage Prevention**:
  - **Buffer Clearance After Tool Confirmation**: Added `self._capture.clear_buffer()` in a `finally` block in `UI.confirm_tool_call()` (`src/zrb/llm/app/ui.py`) to prevent captured stdout from previous operations leaking into future tool results.
  - **User Response Truncation**: Added 500-character limit for user responses in tool confirmation prompts (`src/zrb/llm/tool_call/handler.py`) with truncation notification to prevent excessively long responses from overwhelming the system.

- **Improvement: Core Mandate Task Cancellation Protocol**:
  - **Explicit Cancellation Rules**: Added Task Cancellation section to `mandate.md` with clear rules: (1) Stop when user asks to cancel, (2) Immediate cessation of all tool calls and task execution, (3) No persistence with verification or completion attempts after cancellation.
  - **Tool Denial Response Enforcement**: Enhanced journal documentation with explicit "Tool Denial Response" preference requiring immediate cessation of tool calls when user denies execution with any message.

- **Test Updates**:
  - **Prefix Consistency**: Updated test expectations in `test/llm/summarizer/test_dual_threshold.py` and `test/llm/history_processor/test_history_summarizer.py` to expect uppercase prefixes (`SUMMARY OF TOOL RESULT:` instead of `SUMMARY of tool result:`).
  - **Comprehensive Validation**: All 49 summarizer-related tests pass with updated architecture.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.17 in `pyproject.toml`.

## 2.6.16 (February 26, 2026)

- **Fix: Thread-Safe Interactive Input Handling**:
  - **Graceful Interruption**: Refactored `StdUI.ask_user()` in `src/zrb/llm/agent/std_ui.py` to use `prompt_toolkit.PromptSession().prompt_async()` instead of `asyncio.to_thread(input)`. This prevents the application from hanging indefinitely when a user presses `Ctrl+C` (KeyboardInterrupt) during non-interactive mode tool confirmations. The previous thread-based implementation swallowed signals and blocked the shutdown process.
  - **EOF Error Handling**: Added proper handling for `EOFError` during input, returning an empty string to allow graceful fallback instead of crashing the process.

- **Test Infrastructure Updates**:
  - **Model Mocking**: Fixed an integration test that relied on live API calls by properly mocking the model `openai:gpt-4o-mini` to `test` in `test_tool_policy_integration.py`, preventing timeout errors on network interruptions.
  - **Assertion Resilience**: Updated assertions in `test_llm_task_tool_confirmation.py` to correctly evaluate dynamically wrapped callbacks during tool confirmation tests.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.16 in `pyproject.toml`.

## 2.6.15 (February 26, 2026)

- **Improvement: Core Prompt Refinements & Agent Identity Enhancement**:
  - **Mandate Restructuring**: Updated `mandate.md` with clearer CONTEXT EFFICIENCY principles, better distinction between Directives (action requests) and Inquiries (analysis requests), and improved Execution Framework with explicit Research → Strategy → Execution flow.
  - **Persona Enhancement**: Enhanced `persona.md` with "interactive CLI agent" identity, added High-Signal Output principles (avoid conversational filler, focus on intent), Concise & Direct communication style (aim for <3 lines per response), and Explain Before Acting requirement for state-modifying actions.
  - **Journal Mandate Clarification**: Improved `journal_mandate.md` with clearer guidance on when to read/update journal, emphasis on state snapshots and active constraints, and refined journal curation principles.

- **Improvement: Skill System Overhaul with Validation-First Philosophy**:
  - **Test Skill Enhancement**: Major overhaul of test skill with emphasis on "Validation is the only path to finality" mandate. Added detailed Environment & Pattern Audit workflow, comprehensive test generation guidelines, and Exhaustive Verification requirements (build, lint, type-check in addition to tests).
  - **Debug Skill Refinement**: Enhanced debug skill with Empirical Reproduction First mandate, structured scientific workflow, and improved debugging checklist focusing on empirical verification and surgical fixes.
  - **Brownfield Skill Updates**: Various refinements to core_mandate_brownfield skill for better discovery and execution protocols.

- **Improvement: Tool Safety & Non-Interactive Execution**:
  - **Bash Tool Safety Enhancement**: Added mandate to ALWAYS prefer non-interactive flags (`-y`, `--yes`, `--watch=false`, `CI=true`) for scaffolding tools or test runners to avoid persistent watch modes hanging execution.
  - **Improved Timeout Guidance**: Enhanced timeout error messages with specific guidance on using non-interactive flags to prevent background process issues.

- **Improvement: Agent Guidance Refinements**:
  - **Coder Agent Updates**: Enhanced guidance for safe integration into complex legacy codebases with emphasis on pattern matching and surgical changes.
  - **Generalist & Researcher Agent Refinements**: Updated agent guidance with improved workflow patterns and context efficiency principles.

- **Dependency Updates**:
  - **Core Framework**: pydantic-ai-slim updated from 1.62.0 to 1.63.0.
  - **LLM Providers**: anthropic (>=0.78.0 → >=0.80.0), cohere (>=5.18.0 → >=5.20.6), huggingface-hub (>=0.33.5,<1.0.0 → >=1.3.4,<2.0.0), voyageai (>=0.3.2 → >=0.3.7).
  - **Various transitive dependencies** updated for security and compatibility.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.15 in `pyproject.toml`.


## 2.6.14 (February 26, 2026)

- **Fix: Non-Interactive UI Tool Confirmation for Edit Command**:
  - **ToolCallHandler Integration**: Fixed editing in non-interactive mode by replacing simple policy checker with `ToolCallHandler` in `LLMChatTask._create_llm_task_core()`. The previous implementation used `check_tool_policies()` which only handled tool policies, not response handlers or argument formatters.
  - **Complete Tool Handling**: The fix switches to `ToolCallHandler` which properly handles all three components (tool policies, argument formatters, response handlers) and includes the 'e' (edit) option in the confirmation prompt.
  - **Key Change**: In `src/zrb/llm/task/llm_chat_task.py`, non-interactive mode now uses `ToolCallHandler(tool_policies=self._tool_policies, argument_formatters=self._argument_formatters, response_handlers=self._response_handlers)` instead of a simple async wrapper around `check_tool_policies()`.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.14 in `pyproject.toml`.

## 2.6.13 (February 25, 2026)

- **Improvement: SearxNG Configuration Refactoring & Automatic Management**:
  - **Streamlined Configuration File**: Remove `settings.yml` searxng file.
  - **Automatic Configuration Setup**: Added `copy_searxng_setting` task that automatically copies SearxNG configuration to `~/.config/searxng/` directory if it doesn't exist, ensuring proper configuration management without manual intervention.
  - **Improved Docker Volume Mounting**: Changed working directory from project directory to user home directory (`os.path.expanduser("~")`) for better Docker volume mounting compatibility, allowing the `./config/` volume to correctly map to the user's configuration directory.
  - **Task Integration**: Made `copy_searxng_setting` an upstream dependency of the `start-searxng` task, ensuring configuration is always available before starting the SearxNG container.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.13 in `pyproject.toml`.

## 2.6.12 (February 24, 2026)

- **Improvement: UI Output Redirection Buffering**:
  - **Buffered Stream Capture**: Modified `GlobalStreamCapture` in `src/zrb/llm/app/redirection.py` to buffer stdout/stderr output instead of immediately sending to UI via `ui_callback`. Added `_buffer` list, `get_buffered_output()`, and `clear_buffer()` methods for controlled output management.
  - **Delayed Output Display**: Updated `run_async()` in `src/zrb/llm/app/ui.py` to print buffered output after UI closes (`self._capture.stop()`), providing cleaner UI experience with output appearing after interaction completion.
  - **Tool Streaming Preservation**: Bash tool output continues to stream to UI in real-time via `zrb_print(..., plain=True)` → `append_to_output` direct path (bypasses capture), maintaining responsive tool feedback while buffering library `print()` output.

- **Fix: Hook System Error Handling & Sequential Execution**:
  - **Proper Error Propagation**: Updated `_parse_hook_result()` in `src/zrb/llm/hook/executor.py` to set `error=result.output` and `exit_code=1` when `success=False`, ensuring proper error reporting for failed hook executions.
  - **Sequential Hook Execution**: Changed `execute_hooks()` in `src/zrb/llm/hook/manager.py` from concurrent (`asyncio.gather`) to sequential execution, enabling proper blocking behavior and `continue_execution=False` logic to work correctly.
  - **Enhanced Hook Result Processing**: Improved error handling with proper exception wrapping and continuation logic for failed hooks, maintaining Claude Code compatibility with exit code 2 for blocking decisions.

- **Test Infrastructure: Comprehensive Test Suites**:
  - **OptionInput Test Coverage**: Created comprehensive test suite for `OptionInput` in `test/input/test_option_input.py` with 7 test cases covering public API (initialization, HTML generation, default values, context updates), improving coverage from 25% to 40%.
  - **Lexer ANSI Escape Testing**: Added comprehensive test suite for `CLIStyleLexer` in `test/llm/app/test_lexer.py` with 13 tests covering ANSI escape sequence tokenization (colors, bold, background colors, reset sequences, literal escapes).
  - **Redirection Buffer Testing**: Created comprehensive test suite for `GlobalStreamCapture` in `test/llm/app/test_redirection.py` with 8 test cases covering public API (initialization, start/stop lifecycle, buffer management, pause context manager, original stdout retrieval).
  - **Hook Manager Comprehensive Coverage**: Added extensive test suite in `test/llm/hook/test_manager_comprehensive_coverage.py` with 49 tests covering edge cases, error handling, blocking logic, timeout scenarios, and Claude Code compatibility.

- **Test Results**: All 866 tests pass with 31% overall coverage. Hook test suite passes 49/49 tests after fixes.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.12 in `pyproject.toml`.

## 2.6.11 (February 24, 2026)

- **Refactor: Centralized String Conversion Utility**:
  - **Shared to_string() Function**: Created centralized `to_string()` utility in `src/zrb/util/string/conversion.py` to handle complex data structure conversion to strings with proper JSON serialization for dictionaries and lists.
  - **Eliminated Code Duplication**: Removed `FileHistoryManager._convert_to_string()` method and replaced all `str()` calls in tool return content with `to_string()` for consistent string conversion behavior.
  - **Enhanced Tool Return Safety**: Updated `_create_safe_wrapper()` and `_wrap_toolset()` in `src/zrb/llm/agent/common.py` to use `to_string()` for tool return content, ensuring proper handling of non-string tool results.
  - **Proactive Content Cleaning**: Enhanced `FileHistoryManager._clean_corrupted_content()` to use centralized `to_string()` utility, maintaining proactive cleaning of boolean, number, dict, list, and None values before validation.
  - **JSON Serialization Safety**: The new utility safely handles dictionaries and lists via `json.dumps()` with proper error fallback to `str()` for serialization failures.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.11 in `pyproject.toml`.


## 2.6.10 (February 24, 2026)

- **Fix: PRE_COMPACT Hook Timing**:
  - **Correct Hook Invocation**: Fixed `run_agent.py` to invoke PRE_COMPACT hook BEFORE history summarization/processing, not after agent execution. Hook now receives comprehensive context: `token_count` (calculated via limiter), `message_count`, and `has_history_processors` flag.
  - **Removed Simplistic Check**: Eliminated simplistic message count check (`len(run_history) > 10`) and moved hook invocation to history processing section where it belongs.
  - **Claude Code Compatibility**: Aligns with Claude Code compatibility for hook events, ensuring hooks can prepare/modify history before summarization occurs.
  - **Comprehensive Testing**: All 265 LLM tests pass including 33 hook tests, verifying the fix maintains system stability.

- **Fix: Pydantic AI Boolean Content Corruption**:
  - **Proactive Content Cleaning**: Enhanced `FileHistoryManager` to proactively clean corrupted content (boolean, number, dict, list, None) before validation, not just on ValidationError. Updated `_clean_corrupted_content()` to handle all part types with content fields and added proper None handling (convert to empty string).
  - **Always Clean Strategy**: Implemented "always clean" approach: always clean in `load()` before validation, always clean in `save()` before validation/saving. This prevents boolean corruption issues where pydantic-ai validation might allow boolean values that later cause serialization problems.
  - **Comprehensive Test Updates**: Updated test descriptions from "ValidationError triggers auto-recovery" to "proactively cleaned to string" to reflect new proactive cleaning behavior. Added comprehensive test for None, list, float, and boolean False content conversion.
  - **Test Verification**: All 822 tests pass including comprehensive tests for file history manager corruption handling.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.10 in `pyproject.toml`.

## 2.6.9 (February 23, 2026)

- **Improvement: History Summarizer Algorithm Overhaul**:
  - **Four-Phase Splitting Strategy**: Complete rewrite of `split_history()` in `src/zrb/llm/summarizer/history_splitter.py` with sophisticated 4-phase approach: (1) Search backwards from target window, (2) Search forwards for any safe split, (3) Find largest safe split under 80% token threshold, (4) Best-effort scoring-based approach.
  - **Enhanced Tool Pair Safety**: New `is_split_safe()` function with detailed logic for complete pairs (must stay together), incomplete calls (can be summarized), and orphaned returns (must not be kept). Replaces simpler `validate_tool_pair_integrity`.
  - **Best-Effort Scoring**: `find_best_effort_split()` now uses scoring system to minimize damage to incomplete tool pairs while never breaking complete pairs.
  - **Comprehensive Test Coverage**: Added `test/llm/summarizer/test_summarizer_history_splitter.py` with tests for safe split detection, best-effort splitting, and window-based splitting.

- **Fix: Message Merging Immutability**:
  - **Immutable Message Creation**: Updated `ensure_alternating_roles()` in `src/zrb/llm/message.py` to create new message objects instead of mutating existing ones: `ModelRequest(parts=list(last_msg.parts) + list(msg.parts))` for user messages and `dataclasses.replace()` for assistant messages.
  - **Tool Pair Detection**: Enhanced `get_tool_pairs()` to accurately identify tool call/return relationships for safe split validation.

- **Improvement: File Tool Truncation System**:
  - **Unified Truncation Logic**: Extended head/tail truncation mechanism from `bash.py` to all file tools (`list_files`, `glob_files`, `read_file`, `search_files`, `read_files`) with consistent `preserved_head_lines` and `preserved_tail_lines` parameters.
  - **Intelligent Defaults**: Defaults: 100+150 lines for read operations, 50+50 for search matches, 100+100 for file listings. Search truncation applies at both file-level and within-file matches.
  - **Critical Fix**: Files are now sorted BEFORE truncating (not after) to ensure consistent head/tail selection across executions.

- **Documentation Updates**:
  - **Summarization Logic Documentation**: Updated `docs/core-concepts/summarization-logic.md` to reflect new 4-phase splitting strategy, tool pair safety logic, and immutable message merging.
  - **AGENTS.md Corrections**: Fixed development setup commands and testing guidelines.

- **Test Infrastructure**:
  - **Pytest Output Format**: Simplified `zrb-test.sh` output to `--cov-report="term-missing:skip-covered"` for cleaner test reporting.
  - **Enhanced File History Tests**: Expanded `test_file_history_manager.py` with comprehensive auto-recovery validation tests.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.9 in `pyproject.toml`.

## 2.6.8 (February 22, 2026)

- **Fix: Summarizer Deep Copy Protection & Mutation Prevention**:
  - **Tool Result Safety**: Added `_safe_copy_result()` function in `src/zrb/llm/agent/common.py` to create deep copies of mutable tool results (lists, dicts, sets) while returning immutable objects (strings, numbers, None) as-is, preventing pydantic-ai from modifying original tool results during processing.
  - **ToolReturn Wrapper Enhancement**: Updated `_create_safe_wrapper()` and `_wrap_toolset()` to use safe copies when creating `ToolReturn` objects, ensuring tool results remain immutable throughout agent execution.
  - **Summarization Safety**: Added `_safe_copy_for_summarization()` function in `src/zrb/llm/summarizer/message_processor.py` to create safe copies of content before summarization processing, preventing mutation during JSON serialization and string conversion.
  - **Debug Logging**: Added comprehensive debug logging for large content (>10000 tokens) to help diagnose summarization issues with detailed type information and content samples.

- **Fix: History Splitter Orphaned Return Handling**:
  - **Orphaned Return Logic**: Fixed `find_best_effort_split()` in `src/zrb/llm/summarizer/history_splitter.py` to properly handle orphaned returns (returns without corresponding calls) by rejecting splits that would keep orphaned returns in the history, ensuring Pydantic AI requirements are met.
  - **Pair Integrity Enforcement**: Enhanced logic to detect when orphaned returns would be preserved after a split and reject such splits to maintain tool call/return pair integrity.

- **Improvement: Token Counting Accuracy for Dictionaries**:
  - **Enhanced Dict Processing**: Updated `_to_str()` method in `src/zrb/llm/config/limiter.py` to join key-value pairs with spaces (`"key: value"`) instead of concatenation, improving token counting accuracy for dictionary content.
  - **Better Token Estimation**: The new format provides more realistic token counts for structured data, ensuring rate limiting and context window management work correctly with complex tool results.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.8 in `pyproject.toml`.

## 2.6.7 (February 22, 2026)

- **Improvement: Enhanced Agent Tool Safety & Error Handling**:
  - **Robust ToolReturn Wrapping**: Updated `_create_safe_wrapper()` in `src/zrb/llm/agent/common.py` to consistently return proper `ToolReturn` objects for both successful executions and errors, ensuring compatibility with pydantic-ai's structured response handling.
  - **Toolset Error Consistency**: Enhanced `_wrap_toolset()` to wrap toolset errors in `ToolReturn` objects with error metadata, maintaining consistent error reporting across all tool execution paths.
  - **Backward Compatibility**: Successful tool results are automatically wrapped in `ToolReturn` objects when not already wrapped, while preserving existing `ToolReturn` instances.

- **Improvement: Mandate Refinement & Operational Rigor**:
  - **System Awareness Directive**: Added explicit "System Awareness" principle to CONTEXT-FIRST mandate, requiring agents to discover existing similar functionality before creating new mechanisms, preventing redundant implementations.
  - **Pattern Recognition Principle**: Added "Pattern Recognition" directive mandating agents to identify and follow existing system patterns, avoiding introduction of new patterns without explicit approval.
  - **Discovery First Protocol**: Enhanced Brownfield Protocol to explicitly require "Discovery First" approach, forbidding implementation without empirical verification of system behavior.
  - **Assumption Checking Standard**: Added "Assumption Checking" to Implementation Standards, requiring verification of naming patterns, file locations, and system behavior through code path tracing.
  - **Verification & Completion Mandate**: Introduced new Section 7 with four core principles: No Premature Completion, Empirical Verification, Assumption Validation, and Solution Testing, ensuring rigorous validation before task completion.

- **Test Improvement: Pydantic-AI Type Safety**:
  - **Real Callable Functions**: Updated `test_llm_chat_task_coverage.py` to use real async callable functions instead of `MagicMock` objects, preventing pydantic-ai type inspection errors and improving test reliability.
  - **Tool Factory Testing**: Enhanced tool factory tests to work with actual function objects rather than mocks, ensuring proper tool resolution during agent execution.

## 2.6.6 (February 22, 2026)

- **Architectural: Modular Core Mandate Skills**:
  - **Brownfield Protocol Skill**: Extracted detailed brownfield discovery and execution protocol from the main mandate into `core_mandate_brownfield` skill, providing step-by-step guidance for safe codebase modifications.
  - **Documentation Skill**: Created `core_mandate_documentation` skill encapsulating documentation-as-code principles, ensuring documentation stays synchronized with code changes.
  - **Mandate Streamlining**: Simplified main mandate to reference skills instead of containing verbose protocols, improving token efficiency while maintaining functionality.

- **Documentation: AGENTS.md Complete Restructuring**:
  - **Practical Guide Focus**: Transformed from detailed technical documentation to concise, actionable development guide with clear "What the Project Is", "Development Setup", and "Where to Find Files" sections.
  - **Removed Redundant Sections**: Eliminated verbose LLM-specific technical details (summarization system, message safety) that are better covered in code or specialized skills.
  - **Enhanced Readability**: Organized into logical sections with improved navigation and clearer development conventions.

- **Tool Documentation Standardization**:
  - **Consistent MANDATES Format**: Updated all LLM tool docstrings (`bash.py`, `code.py`, `file.py`, `web.py`, `delegate.py`, `skill.py`, `zrb_task.py`) to use concise "MANDATES:" format instead of verbose operational guidance.
  - **Improved Clarity**: Each tool now has clear, scannable mandates that communicate essential constraints without overwhelming detail.
  - **Backward Compatibility**: Maintains full functionality while improving agent comprehension and token efficiency.

- **Agent System Refinements**:
  - **Enhanced Agent Descriptions**: Added "Delegate to this agent for..." context to all agent definitions (`coder`, `explorer`, `generalist`, `planner`, `researcher`, `reviewer`) for clearer delegation guidance.
  - **Note Tool Removal**: Removed deprecated note tools (`ReadContextualNote`, `WriteContextualNote`, `ReadLongTermNote`, `WriteLongTermNote`) from agent tool lists, aligning with journal-based context management.
  - **Skill Description Improvements**: Added "Use when..." context to all skill descriptions for better user guidance.

- **Configuration & Bug Fixes**:
  - **Tool Policy Fix**: Fixed `_approve_if_path_inside_parent` in `chat_tool_policy.py` to return `True` when no path is found, preventing unnecessary denials.
  - **PromptManager Enhancement**: Updated to properly handle `include_claude_skills` parameter and filter core mandate skills appropriately.
  - **Code Cleanup**: Removed redundant comments and simplified `SubAgentManager` initialization logic.

- **Test Updates**:
  - **Simplified Prompt Tests**: Removed path-specific warning tests from `test_prompt_util.py` as warnings are now handled at the skill level.
  - **Maintenance**: Updated test expectations to align with new tool documentation format.

## 2.6.5 (February 21, 2026)

- **Refactor: Centralized LLM Message Safety**:
  - **Unified Message Logic**: Created `src/zrb/llm/message.py` to centralize message validation and manipulation logic, removing duplication across the codebase.
  - **Strict Role Alternation**: Implemented `ensure_alternating_roles` to automatically merge consecutive messages of the same role (e.g., User -> User), ensuring strict compliance with LLM API requirements (especially Anthropic).
  - **Tool Pair Integrity**: Centralized `get_tool_pairs` and `validate_tool_pair_integrity` to ensure `ToolCall` and `ToolReturn` messages are never separated during history processing or summarization.
  - **Workflow Integration**: Integrated these safety checks directly into `run_agent` and `history_summarizer` to prevent API errors at the source.

- **Cleanup & Optimization**:
  - **Codebase cleanup**: Removed unused imports and redundant logic in `message_processor.py` and `history_splitter.py`.
  - **Test Suite Optimization**: Removed obsolete `test_role_alternation.py` in favor of comprehensive new tests in `test/llm/test_message.py`.
  - **Documentation**: Updated `AGENTS.md` with a new "LLM Message Safety" section detailing the core principles of role alternation and tool integrity.

## 2.6.4 (February 21, 2026)

- **Feature: PromptManager Configuration Defaults**:
  - **Configurable Prompt Components**: Added 8 new configuration properties to `CFG` for controlling PromptManager behavior: `LLM_INCLUDE_PERSONA`, `LLM_INCLUDE_MANDATE`, `LLM_INCLUDE_GIT_MANDATE`, `LLM_INCLUDE_SYSTEM_CONTEXT`, `LLM_INCLUDE_JOURNAL`, `LLM_INCLUDE_CLAUDE_SKILLS`, `LLM_INCLUDE_CLI_SKILLS`, `LLM_INCLUDE_PROJECT_CONTEXT`.
  - **Flexible Parameter Handling**: Updated `PromptManager.__init__()` to accept `None` for boolean parameters, allowing them to fall back to configuration defaults while preserving explicit override capability.
  - **Backward Compatibility**: Maintains full compatibility with existing code - explicit `True`/`False` values continue to work as before.
  - **Environment Variable Support**: All properties can be configured via environment variables (e.g., `ZRB_LLM_INCLUDE_PERSONA=0`) using standard "1"/"0" or "on"/"off" string format.

- **Improvement: Documentation as Code**:
  - **Updated Mandate**: Added "Documentation as Code" section to mandate, requiring documentation to be treated as first-class code that must be updated when code changes.
  - **Configuration Documentation**: Added new configuration options to official documentation with clear defaults and usage examples.
  - **Customization Guide Update**: Enhanced customizing AI assistant documentation with information about PromptManager configuration defaults.

## 2.6.3 (February 19, 2026)

- **Feature: Dynamic Session Log Directory Resolution**:
  - **Flexible Directory Configuration**: Enhanced `FileSessionStateLogger` to accept both string and callable for `session_log_dir` parameter, enabling dynamic directory resolution at runtime.
  - **Backward Compatibility**: Maintained full backward compatibility with existing string inputs while adding support for callable functions that return directory paths.
  - **Factory Integration**: Updated `session_state_logger_factory.py` to use lambda wrapper for `CFG.SESSION_LOG_DIR`, demonstrating callable usage pattern.
  - **Clean Abstraction**: Added `_get_session_log_dir()` method to abstract evaluation logic, ensuring consistent path resolution throughout the class.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.3 in `pyproject.toml`.

## 2.6.2 (February 19, 2026)

- **Improvement: Enhanced Prompt Expansion with Path-Specific Warnings**:
  - **Modular Refactoring**: Refactored `expand_prompt()` utility into modular functions (`_get_path_references`, `_process_path_reference`, `_create_appendix_entry`, `_create_appendix_header`) for better maintainability and testability.
  - **Path-Specific Warnings**: Added intelligent warning messages that differentiate between file and directory references. File references now warn against using `read_file`, while directory references warn against using `list_files`, improving agent guidance.
  - **Comprehensive Testing**: Added 6 new test cases (`test/util/llm/test_prompt_util.py`) covering file-specific warnings, directory-specific warnings, mixed references, and edge cases.

- **Improvement: Streamlined Documentation & Prompt Refinements**:
  - **Concise Documentation Summaries**: Reduced maximum summary length from 10,000 to 5,000 characters in `create_project_context_prompt()` and simplified warning text for better clarity.
  - **Mandate Simplification**: Streamlined strategic reasoning section and added "In-Place Refactoring" principle emphasizing direct file modification over creating new files.
  - **Persona Refinement**: Condensed persona description for better token efficiency while maintaining core identity as "Brownfield Specialist" and "Pragmatic Doer".
  - **Journal System Enhancement**: Renamed to "Journal System: The Polymath's Codex" with emphasis on "Rhizomatic Linking" and proactive knowledge capture as a "Living Knowledge Base".

- **Feature: Git-Aware System Context**:
  - **New Git Utility**: Added `is_inside_git_dir()` function in `src/zrb/llm/util/git.py` for checking git repository status without redundant subprocess calls.
  - **Conditional Git Mandate**: Updated `PromptManager` to only include git mandate when inside a git repository, preventing unnecessary content in non-git contexts.
  - **Optimized System Context**: Enhanced `system_context.py` to use new git utility and improve file categorization logic.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.2 in `pyproject.toml`.

## 2.6.1 (February 18, 2026)

- **Fix: Pydantic-AI Toolset Integration Compatibility**:
  - **Signature Mismatch Resolution**: Fixed `TypeError` when adding MCP toolsets to `llm_chat` by updating `SafeToolsetWrapper.call_tool()` signature to match pydantic-ai's `WrapperToolset` base class (version 1.60.0).
  - **Parameter Alignment**: Changed signature from `(self, tool_name: str, tool_input: Any, ctx: Any) → ToolReturn` to `(self, name: str, tool_args: dict[str, Any], ctx: Any, tool: Any) → Any`.
  - **MCP Toolset Support**: Resolves errors when loading MCP toolsets via `load_mcp_config()` and adding them to LLM chat sessions, ensuring proper forwarding of all arguments to parent toolset implementations.

## 2.6.0 (February 18, 2026)

- **Feature: Robust LLM History Summarization**:
  - **Role Alternation Enforcement**: Implemented strict role alternation (User/Assistant) in `history_summarizer` to comply with LLM provider constraints (e.g., Pydantic AI), preventing consecutive same-role messages by merging them.
  - **Tool Call/Return Integrity**: Enhanced history splitting logic to ensure Tool Call and Tool Return pairs are never separated during summarization or truncation, preventing orphaned tool returns.
  - **Redundant Prompt Removal**: Deprecated and removed `summarizer.md` in favor of `conversational_summarizer.md`, consolidating prompt logic.
  - **Summarization Refactor**: Moved core summarization logic from `history_processor` to `llm.summarizer` package for better organization.

- **Quality Assurance**:
  - **Test Coverage Expansion**: Added comprehensive test suites (`test_role_alternation.py`, `test_summarizer_extra.py`) covering edge cases in summarization, tool pairing, and text chunking, achieving >75% code coverage.
  - **Utility Tests**: Added extra tests for `banner`, `callable`, `load`, `yaml`, and `todo` utilities.

## 2.5.3 (February 17, 2026)

- **Refactor: Journal Prompt System Migration to Markdown Templates**:
  - **Static Template Replacement**: Replaced dynamic `create_journal_prompt()` function with static `journal.md` markdown template, aligning with existing prompt system pattern (persona.md, mandate.md).
  - **Prompt Manager Update**: Updated `PromptManager` to use `get_journal_prompt()` instead of middleware factory, simplifying journal prompt implementation.
  - **Enhanced Tool Policies**: Added auto-approve policies for Write, WriteMany, and Edit tools when operating within journal directory, enabling seamless journal maintenance.
  - **Persona Refinement**: Updated "Polymath Executor" persona with stronger emphasis on hands-on, brownfield development expertise and reduced strategic delegation bias.
  - **Test Migration**: Migrated journal prompt tests from `test_journal.py` to `test_prompt_journal.py` with comprehensive coverage for new markdown-based implementation.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.5.3 in `pyproject.toml`.

## 2.5.2 (February 17, 2026)

- **Fix: Circular Dependency Resolution in LLM Tool Imports**:
  - **Circular Dependency Elimination**: Reorganized LLM tool imports in `src/zrb/llm/agent/manager.py` to resolve circular dependency issues by moving tools from a flat import structure to specialized modules:
    - `analyze_code` → `zrb.llm.tool.code`
    - File-related tools (`analyze_file`, `glob_files`, `list_files`, `read_file`, `read_files`, `replace_in_file`, `search_files`, `write_file`, `write_files`) → `zrb.llm.tool.file`
    - `run_shell_command` → `zrb.llm.tool.bash`
    - `open_web_page` and `search_internet` → `zrb.llm.tool.web`
  - **Backward Compatibility**: Maintained full functionality while preventing import cycles that could cause runtime errors.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.5.2 in `pyproject.toml`.

## 2.5.1 (February 17, 2026)

- **Feature: Enhanced SubAgentManager API Consistency**:
  - **append_tool Methods**: Added `append_tool()` and `append_tool_factory()` methods to `SubAgentManager` to match the `LLMTask` pattern, ensuring API consistency across the codebase.
  - **Toolset Support**: Enhanced `SubAgentManager` with comprehensive toolset management including `append_toolset()`, `append_toolset_factory()`, and `_get_all_toolsets()` methods for better toolset integration.
  - **Backward Compatibility**: Refactored existing `add_tool()` and `add_tool_factory()` methods to delegate to their `append_*` counterparts, maintaining full backward compatibility.
  - **Delegate Tool Export**: Added `create_delegate_to_agent_tool` to public exports in `src/zrb/llm/tool/__init__.py` for easier access.

- **Improvement: Persona Refinement**:
  - **Typo Fix**: Corrected "Orchstrator" to "Orchestrator" in the agent persona for better professionalism and clarity.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.5.1 in `pyproject.toml`.
  - **Dependency Updates**: Updated poetry.lock with Poetry 2.3.1 and minor dependency specifier changes for consistency.

## 2.5.0 (February 16, 2026)

- **Feature: Sub-Agent System Refactoring with Automatic Discovery**:
  - **Automatic Agent Discovery**: Replaced manual `create_sub_agent_tool()` with automatic discovery of agents defined in JSON/YAML files within the `agents/` directory. SubAgentManager now automatically loads agent definitions from the filesystem.
  - **Unified Delegation Tool**: Enhanced `DelegateToAgent` tool to work with the new agent discovery system. Added `zrb_is_delegate_tool` flag to prevent infinite recursion in nested delegation scenarios.
  - **Tool Filtering & Recursion Prevention**: SubAgentManager now filters out delegate tools from sub-agents to prevent infinite recursion loops. Added comprehensive tests for tool filtering behavior.
  - **Configuration Cleanup**: Removed deprecated `LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD` environment variable, consolidating to use only `LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`.
  - **Default Tool Integration**: SubAgentManager automatically includes standard tools (file operations, web search, etc.) while maintaining separate tool instances from the main agent to prevent state conflicts.
  - **Documentation Updates**: Rewrote LLM task documentation to showcase new agent definition format with JSON/YAML examples. Updated configuration documentation with simplified environment variables.

- **Breaking Changes**:
  - **Removed `create_sub_agent_tool()`**: Function is completely removed. Users must migrate to JSON/YAML agent definitions in the `agents/` directory.
  - **Removed `LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD`**: Environment variable is no longer supported. Use `LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD` instead.
  - **Changed Default Behavior**: Manual tool registration for sub-agents is replaced with automatic discovery and filtering.

- **Migration Path**:
  1. Move sub-agent definitions to JSON/YAML files in `agents/` directory.
  2. Update code to use `DelegateToAgent` tool instead of `create_sub_agent_tool`.
  3. Update environment variables to remove deprecated `LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD`.

## 2.4.2 (February 16, 2026)

- **Improvement: LLM Limiter Token Counting Optimization**:
  - **Performance Enhancement**: Refactored `LLMLimiter._to_str()` method to avoid JSON serialization overhead for large collections, implementing direct string concatenation for lists and dictionaries.
  - **Memory Efficiency**: Added `skip_instructions` parameter to align with Pydantic AI's behavior of only counting current instructions (historical instructions are not replayed to the model).
  - **Reduced Overhead**: Updated test expectations to reflect reduced string length from ~20k to <10k characters for nested structures, demonstrating significant performance improvement.
  - **Better Pydantic AI Integration**: Enhanced handling of complex message structures with separate processing for parts, instructions, content, and args fields.

- **Improvement: Agent Delegation & Operational Clarity**:
  - **Enhanced Persona**: Updated agent persona from "Polymath Agent" to "Lead Architect and Polymath Orchestrator" with stronger emphasis on strategic command and surgical delegation.
  - **Refined Mandate**: Clarified DEEP PATH delegation with explicit "SURGICAL SCOPE" directive, requiring narrow, atomic tasks for sub-agents and prohibiting "explore and fix" patterns.
  - **Improved Recovery Protocol**: Enhanced delegation failure handling with better context management and redundant history purging during forced execution.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.4.2 in `pyproject.toml`.
  - **Dependency Normalization**: Minor version format updates in `poetry.lock` for consistency.

## 2.4.1 (February 16, 2026)

- **Feature: Robust LLM Summarization & History Management**:
  - **Dual-Threshold Summarization Logic**: Implemented separate thresholds for individual large messages and total conversational history to prevent context window overflows and "insanity" during long sessions.
  - **Role Alternation Enforcement**: Added `_ensure_alternating_roles` to the history processor, ensuring that the conversation history always follows the User -> Assistant pattern required by LLM providers.
  - **Recursive Guard & Loop Prevention**: Added a recursion depth guard (max 5) and progress verification to `summarize_long_text` to prevent infinite summarization loops.
  - **Safe Tool-Call Splitting**: Enhanced history splitting logic to ensure tool call/result pairs are never orphaned, maintaining the integrity of Pydantic AI message sequences.

- **Improvement: Token Counting Efficiency & Performance**:
  - **Fixed O(N²) Token Counting**: Refactored `LLMLimiter._to_str` to use `json.dumps` for collections, resolving a critical performance bottleneck that caused exponential latency as history grew.
  - **Accurate Token Estimation**: Improved handling of complex message structures to ensure rate limiting remains precise even with large tool outputs.

- **Refinement: Summarizer Prompt & State Logic**:
  - **Goal Evolution System**: Updated `summarizer.md` with logic to detect when objectives are met and pivot the agent's focus, preventing "conclusion loops."
  - **XML Safety & Formatting**: Wrapped state snapshot components in CDATA sections to prevent XML parsing errors and ensured "Silent Thinking" for more reliable structured output.
  - **Explicit Security Rules**: Hardened the summarizer prompt against adversarial content and formatting distractions within the history.

- **Maintenance & Test Infrastructure**:
  - **Expanded Coverage**: Added 4 new specialized test suites:
    - `test_dual_threshold.py`: Verifies message-level vs context-level summarization.
    - `test_sequence_alternation.py`: Confirms role-alternation compliance.
    - `test_integration_summarization.py`: Validates end-to-end history distilling.
    - `test_limiter_explosion.py`: Stress-tests the token counting performance fix.
  - **Agent Guide Update**: Updated `AGENTS.md` (Section 6) with detailed technical documentation of the summarization system.
  - **Version Bump**: Updated to version 2.4.1 in `pyproject.toml`.
  - **Stabilized Config Tests**: Fixed stale tests in `test/config/test_config.py` related to journal directory settings.

## 2.4.0 (February 16, 2026)

- **Feature: Directory-Based Journal System with Simplified CFG Access**:
  - **New Journal System**: Replaces old NoteManager with directory-based journaling
    - Uses `CFG.LLM_JOURNAL_DIR` and `CFG.LLM_JOURNAL_INDEX_FILE` directly (no abstraction)
    - Only `index.md` auto-injected into prompts via placeholder replacement (e.g., `{CFG_LLM_JOURNAL_DIR}`)
    - Journal prompt component creates directory/file if missing
    - Default location: `~/.zrb/llm-notes/` with `index.md` as default index file
  - **Breaking Changes**: Removed old note system completely
    - Deleted `src/zrb/llm/note/` directory and all related files
    - Deleted `src/zrb/llm/tool/note.py` and `src/zrb/llm/prompt/note.py`
    - Removed all note-related tests (9 trivial tests)
    - **Completely removed `LLM_NOTE_FILE` configuration** (not just deprecated)
  - **Enhanced Prompt System**: Updated prompt placeholder replacement
    - Added `_get_prompt_replacements()` and `_replace_prompt_placeholders()` functions
    - All prompts now support `{CFG_*}` placeholders for dynamic configuration injection
    - Supports `{CFG_LLM_JOURNAL_DIR}`, `{CFG_LLM_JOURNAL_INDEX_FILE}`, `{CFG_ROOT_GROUP_NAME}`, `{CFG_LLM_ASSISTANT_NAME}`, `{CFG_ENV_PREFIX}`
  - **Comprehensive Testing**: Added 6 tests for journal prompt component
    - Covers empty journal, content injection, missing directory/file creation
    - Includes edge case where no sections are added (line 57 coverage)
    - All 6 tests pass with comprehensive coverage

- **Improvement: Code Coverage & Testing Infrastructure**:
  - **Achieved ≥75% Overall Code Coverage**: Improved from 74% to 75%
    - Added tests for `src/zrb/util/cmd/remote.py` (improved from 20% to 100%)
    - Added tests for `src/zrb/util/cli/subcommand.py` (improved from 78% to 100%)
    - All 758 tests pass with 8 warnings
  - **Updated Testing Documentation**: Enhanced AGENTS.md with comprehensive testing instructions
    - Added Section 5 "Testing" with detailed command usage
    - Test command: `source .venv/bin/activate && ./zrb-test.sh <parameter>`
    - Coverage goal: Maintain ≥75% overall code coverage
    - Test structure and conventions documented

- **Documentation & Configuration Updates**:
  - **Updated AGENTS.md**: Added journal system documentation (Section 3.5)
    - Purpose: Directory-based journaling for agents to maintain context across sessions
    - Location: `~/.zrb/llm-notes/` (configurable via `CFG.LLM_JOURNAL_DIR`)
    - Index File: `index.md` (configurable via `CFG.LLM_JOURNAL_INDEX_FILE`) auto-injected into prompts
    - Organization: Hierarchical structure by topic with concise index references
    - Documentation separation: AGENTS.md for technical docs, journal for non-technical notes
  - **Updated Mandate**: Refined context management guidelines
    - Changed from note-based to journal-based context management
    - Added journal system configuration details to mandate
    - Emphasized documentation separation between AGENTS.md and journal
  - **New Configuration Options**:
    - `LLM_JOURNAL_DIR`: Directory for journal files (default: `~/.zrb/llm-notes/`)
    - `LLM_JOURNAL_INDEX_FILE`: Index filename (default: `index.md`)
  - **Removed Configuration**:
    - `LLM_NOTE_FILE`: Old note file configuration (completely removed from source code)

- **Architectural Refinements**:
  - **Simplified Prompt Manager**: Updated `PromptManager` to use journal instead of note system
    - Changed `include_note` parameter to `include_journal`
    - Removed `note_manager` parameter
    - Updated imports and middleware registration
  - **Clean Imports**: Removed all note-related imports from `__init__.py` files
  - **Consistent Singleton Pattern**: Updated AGENTS.md to reflect `Hook` instead of `Note` as module-level singleton

## 2.3.5 (February 15, 2026)

- **Feature: Enhanced Agent System with Comprehensive Test Coverage**:
  - **Agent Manager Improvements**: 
    - Integrated history summarization processor into agent creation for better context management
    - Added proper context initialization for sub-agents with SharedContext support
    - Fixed import ordering and type hinting issues for better code organization
  - **Summarizer Enhancements**:
    - Added default configuration handling for summary window parameter
    - Improved token threshold logic for conversational summarization with proper fallback to configuration defaults
  - **Mandate Documentation Refinement**:
    - Clarified FAST PATH vs DEEP PATH delegation criteria with explicit context saturation risk assessment
    - Added recovery protocol for failed delegation scenarios to prevent brute-force execution
    - Emphasized user visibility awareness for sub-agent outputs with clear reporting requirements
  - **Comprehensive Test Coverage Expansion**:
    - Added 20+ new test files across all major components (1329 insertions, 31 deletions)
    - Extensive coverage for agent manager, run agent, history processors, hooks, prompts, and tools
    - Resilience tests for summarizer functionality with edge case handling
    - Coverage for config, input, runner, and utility modules ensuring system-wide stability
  - **Minor Documentation Updates**:
    - Refined persona and summarizer prompt templates for better agent guidance
    - Updated tool delegation with proper imports and error handling

## 2.3.4 (February 15, 2026)

- **Bug Fix: Token Counting Robustness for Complex Message Structures**:
  - **Enhanced `_to_str()` Method**: Refactored `LLMLimiter._to_str()` in `src/zrb/llm/config/limiter.py` to handle complex Pydantic AI message structures more robustly:
    - Added proper handling for basic types (int, float, bool, None)
    - Used `getattr()` with safe defaults instead of direct attribute access
    - Added recursive dictionary handling for nested structures
    - Improved resilience against malformed or unexpected message formats
  - **Token Estimation Stability**: Fixed potential token counting inaccuracies when processing tool calls, tool returns, and complex message parts, ensuring more accurate rate limiting and context window management.

- **Improvement: Test Code Quality & Formatting**:
  - **Enhanced Retry Test Suite**: Updated `test_llm_task_retry.py` with improved imports, better formatting, and more comprehensive assertions for error handling scenarios.
  - **Code Style Consistency**: Applied consistent formatting across test files (`test_config.py`, `test_history_summarizer.py`) with proper line breaks and import organization.
  - **Test Coverage Validation**: Added property access tests in `test_config.py` to ensure all configuration properties are accessible without errors.

## 2.3.3 (February 15, 2026)

- **Feature: LLM Task Error Retry with History Preservation**:
  - **Error History Attachment**: Modified `run_agent()` to attach conversation history (`zrb_history`) to exceptions, enabling retry attempts with full context preservation.
  - **LLMTask Retry Logic**: Enhanced `LLMTask._exec_action()` to:
    - Save error details to history before raising exceptions
    - Include retry attempt count in subsequent prompts (`[System] This is retry attempt N`)
    - Maintain conversation continuity across retries
    - Detect duplicate user messages in history to avoid repetition
  - **Automatic Error Handling**: Added `_handle_run_error()` method to automatically append tool return results and error messages to conversation history for recovery.
  - **Context Attempt Property**: Added `attempt` property to `AnyContext` and `Context` classes for tracking retry attempts.

- **Improvement: Code Refactoring & Modularization**:
  - **LLMTask Method Extraction**: Refactored monolithic `_exec_action()` into modular methods:
    - `_get_history_manager()` - History manager initialization
    - `_should_summarize()` - Conversation summarization logic
    - `_create_agent()` - Agent creation
    - `_create_event_handler()` - Event handler setup
    - `_get_effective_prompt()` - Retry-aware prompt generation
    - `_handle_run_error()` - Error history processing
    - `_post_process_output()` - Output cleanup
  - **Enhanced Run Agent Safety**: Wrapped `run_agent()` execution loop in try-except to ensure history attachment to exceptions.

- **Improvement: Test Consolidation & Coverage**:
  - **New Retry Test Suite**: Added comprehensive `test_llm_task_retry.py` verifying:
    - Error history preservation and attachment
    - Automatic history saving on failures
    - Retry attempt tracking in prompts
    - Conversation continuity across retries
  - **Test File Consolidation**:
    - Renamed `test_summarizer_comprehensive.py` → `test_history_summarizer.py`
    - Renamed `test_hook_manager_comprehensive.py` → `test_hook_manager.py`
    - Removed redundant `test_summarizer_logic.py`, `test_config_extended.py`, `test_cli_extended.py`
  - **Enhanced Test Coverage**: Updated existing test files (`test_config.py`, `test_cli.py`) with improved assertions and edge case handling.

- **Improvement: Core Prompt Refinements**:
  - **Updated Mandate & Persona**: Minor refinements to `mandate.md` and `persona.md` for clearer operational directives and improved agent behavior guidelines.
  - **Note Tool Enhancement**: Updated `note.py` tool with improved error handling and user feedback.

## 2.3.2

- **Feature: Enhanced LLM Challenge Framework**:
  - **New Integration-Bug Challenge**: Added comprehensive "integration-bug" challenge type with banking system scenario to test agent ability to identify and fix integration issues between multiple components.
  - **Modular Feature Challenge Architecture**: Refactored feature challenge from monolithic `todo_app.py` to proper FastAPI application structure (`app/database.py`, `app/models.py`, `app/main.py`) for more realistic development testing.
  - **Standardized Verification Scripts**: Updated all challenge verification scripts for consistency and improved error handling across bug-fix, feature, refactor, and research challenge types.

- **Improvement: Specialized Agent System**:
  - **Coder Agent Redefinition**: Transformed coder agent into "Senior Staff Engineer and Brownfield Expert" with focus on safe legacy integration and zero-regression modifications.
  - **New Explorer Agent**: Added discovery specialist for rapid, read-only mapping of unfamiliar codebases and system structures.
  - **New Generalist Agent**: Created polymath executor capable of direct action across all domains for complex multi-step tasks.
  - **Enhanced Planner, Researcher & Reviewer Agents**: Updated directives and tooling for improved architectural planning, evidence-based research, and rigorous code review.

- **Improvement: LLM Evaluation & Benchmarking**:
  - **Expanded Experiment Results**: Updated comprehensive evaluation across 10+ LLM providers (DeepSeek, Google Gemini variants, OpenAI GPT variants, Ollama models) with latest performance metrics.
  - **Enhanced Reporting**: Updated `REPORT.md` with detailed timing, tool usage, and success rates for all challenge types including new integration-bug category.
  - **Baseline Experiment Directories**: Added standardized experiment directories for bug-fix, feature, refactor, and research challenges to facilitate consistent benchmarking.

- **Improvement: Core Prompt Refinements**:
  - **Updated Mandate & Persona**: Refined `mandate.md` and `persona.md` with clearer operational directives and improved agent behavior guidelines.
  - **Structured Agent Definitions**: Enhanced agent markdown files with more specific tool sets, operational mandates, and specialized personas.

## 2.3.1

- **Improvement: Assertive Operational Mandates**:
  - **Imperative Prompting**: Rebuilt core persona (`persona.md`) and mandate (`mandate.md`) using strict **MUST ALWAYS** and **NEVER** directives, transitioning from descriptive guidance to non-negotiable engineering mandates.
  - **Tool Selection Hierarchy**: Mandated a strict discovery hierarchy (`Read` > `Glob` > `LS`) to eliminate redundant token consumption and prevent "blind exploration" when paths are already known.
  - **Verification Loop**: Upgraded implementation steps into a mandatory **Plan -> Act -> Validate** cycle, forbidding assumed success without test/linter verification.

- **Feature: "High-Signal" Memory Management**:
  - **Atomic Note Mandate**: Strictly instructed the agent to save only small, high-signal, and rarely-changing architectural facts or user preferences to `WriteContextualNote` and `WriteLongTermNote`.
  - **Read-before-Write Workflow**: Mandated checking existing notes before updates to prevent context loss or redundant duplication.
  - **Context Restoration**: Improved state snapshots to prioritize evidence-backed insights over raw history preservation.

- **Improvement: Technical Tool Optimization**:
  - **Enhanced AnalyzeCode**: Added `include_patterns` parameter for granular search control and mandated the use of `extensions` and glob patterns to limit search space.
  - **Refined Search Tools**: Updated `search_files` (Grep) and `analyze_file` docstrings with strict efficiency mandates and usage warnings.
  - **Research Rigor**: Enforced an "OpenWebPage Mandate" for research tasks, requiring full content verification of all search snippets and mandatory citation of verified sources.

- **Improvement: TUI & UX Refinement**:
  - **Focus & Navigation**: Added F6 key to toggle focus between input and output fields and removed redundant TAB navigation hints.
  - **Smooth Scrolling**: Implemented smarter scrolling logic that keeps the latest content in view when the input field is focused or when already at the bottom of the buffer.
  - **Refresh Stability**: Increased UI refresh rate to `0.1s` for smoother streaming and reduced visual artifacts during reasoning.

## 2.3.0

- **Refactor: Tool Registry Removal & Explicit Tool Registration**:
  - **Tool Registry Removal**: Eliminated the centralized `ToolRegistry` class (`src/zrb/llm/tool/registry.py`) in favor of explicit, direct tool registration for better clarity and control.
  - **Explicit Tool Registration**: Tools are now explicitly added to both `LLMChatTask` and `SubAgentManager` instead of being loaded from a registry, improving transparency and reducing indirection.
  - **Enhanced Agent Manager**: Updated `SubAgentManager` to support explicit tool and tool factory registration, enabling better control over tool availability for sub-agents.
  - **Tool Factory Support**: Added comprehensive support for tool factories in both `LLMChatTask` and `SubAgentManager`, allowing dynamic tool resolution based on runtime context.

- **Improvement: Modular Note Tool Architecture**:
  - **Separate Tool Factories**: Refactored note tools into individual factory functions (`create_read_long_term_note_tool`, `create_write_long_term_note_tool`, `create_read_contextual_note_tool`, `create_write_contextual_note_tool`) for better modularity and testability.
  - **Proper Tool Naming**: Each note tool now explicitly sets its `__name__` attribute to ensure consistent tool identification in the LLM interface.
  - **Comprehensive Testing**: Added new test suite (`test/llm/tool/test_note.py`) with thorough coverage for all note tool operations including long-term and contextual note reading/writing.

- **Feature: Enhanced Tool Safety Policies**:
  - **Path-Based Approval**: Introduced `approve_if_path_inside_cwd` tool policy function that automatically approves file operations only when target paths are within the current working directory, improving security for file system interactions.
  - **Chat Tool Policy Integration**: Added new `chat_tool_policy.py` module with robust path validation logic to prevent unauthorized file access.

- **Improvement: LLM Chat Configuration**:
  - **Simplified Tool Loading**: Streamlined tool initialization in `llm_chat` task by removing registry-based loading and implementing direct tool registration.
  - **Consistent Tool Availability**: Ensured all tools are available to both main chat agent and sub-agents through synchronized registration to both `LLMChatTask` and `SubAgentManager`.
  - **Removed Redundant Tests**: Cleaned up test suite by removing `test_registry_extended.py` which tested the now-removed registry functionality.

- **Maintenance: Dependency Updates**:
  - **Version Bump**: Updated to version 2.3.0 in `pyproject.toml`.
  - **Lock File Refresh**: Updated `poetry.lock` with latest dependency resolutions.

## 2.2.15

- **Feature: Tool Call Validation Policies**:
  - **Read File Validation**: Added `read_file_validation_policy` to automatically reject `Read` tool calls if the target file does not exist, providing immediate feedback to the agent.
  - **Read Many Files Validation**: Added `read_files_validation_policy` to reject `ReadMany` tool calls if none of the specified files are found on the system.
  - **Edit Validation**: Added `replace_in_file_validation_policy` that proactively rejects `Edit` tool calls if:
    - `old_text` and `new_text` are identical.
    - The target file does not exist.
    - The `old_text` to be replaced is not found in the file content.

- **Improvement: LLM Chat Reliability**:
  - **Integrated Validation**: Automatically applied the new validation policies to the built-in `llm_chat` task, reducing failed tool executions and improving agent recovery.

- **Refactor: Tool Call Component Organization**:
  - **Standardized Naming**: Renamed tool call components for better clarity and consistency:
    - `replace_in_file.py` → `replace_in_file_formatter.py` (Argument Formatter)
    - `write_file.py` → `write_file_formatter.py` (Argument Formatter)
    - `replace_in_file.py` → `replace_in_file_response_handler.py` (Response Handler)

- **Maintenance: Comprehensive Testing**:
  - Added new test suites in `test/llm/tool_call/` for all new validation policies (`test_read_file_validation.py`, `test_read_files_validation.py`, `test_replace_in_file_validation.py`).

## 2.2.14

- **Improvement: Enhanced LLM Chat UI/UX**:
  - **Improved Clipboard Handling**: Added robust fallback to in-memory clipboard when `pyperclip` is unavailable, preventing crashes on systems without clipboard support.
  - **Better Navigation Controls**: Added F6 key to toggle focus between input and output fields, and improved Tab/Shift+Tab navigation between UI elements.
  - **Enhanced Output Field Scrolling**: Implemented proper cursor position preservation during content updates, ensuring smooth scrolling experience.
  - **Prevent Interruptions During Thinking**: Blocked new messages, custom commands, and execution commands while the LLM is processing, preventing state corruption.

- **Improvement: Keybinding & Input Refinements**:
  - **Smart Focus Management**: Modified printable character redirection to only occur when no text is selected in the output field, allowing text copying without losing selection.
  - **Better History Navigation**: Restricted Up/Down arrow history navigation to only work when no completion menu is visible, preventing conflicts with autocomplete.
  - **Enhanced Multiline Handling**: Improved handling of multiline inputs with trailing backslashes and better Enter key behavior.

- **Bug Fix: ANSI Escape Sequence Handling**:
  - **Robust Lexer Updates**: Enhanced the CLI style lexer to properly handle both real ESC characters (`\x1B`) and literal string representations (`\033`) in ANSI escape sequences.
  - **Accurate Banner Width Calculation**: Updated ASCII art banner generation to correctly calculate visible length excluding ANSI escape codes, ensuring proper alignment.

- **Improvement: ASCII Art & Visual Presentation**:
  - **Proper ANSI-Aware Padding**: Modified banner padding logic to account for ANSI escape sequences when calculating visual width, preventing misaligned ASCII art displays.
  - **Consistent Output Formatting**: Added global line prefix function to ensure consistent indentation of command outputs in the chat history.

## 2.2.13

- **Bug Fix: Robust Thinking Tag Removal**:
  - **Nested Tag Handling**: Fixed critical bug in thinking tag removal logic that incorrectly handled nested `<thinking>` tags. The original regex-based approach matched from the first opening tag to the first closing tag, causing nested content to be incorrectly preserved.
  - **New Utility Module**: Created `src/zrb/util/string/thinking.py` with `remove_thinking_tags()` function that uses a stack-based parser to properly handle nested tags, unclosed tags, and mixed `<thinking>`/`<thought>` tags.
  - **Comprehensive Testing**: Added 12 test cases covering all edge cases including nested tags, malformed XML, legitimate tag text in content, and performance with large text.
  - **Backward Compatibility**: Maintained existing behavior while fixing the core issue, ensuring all existing tests continue to pass.

- **Improvement: Summarizer Refactoring & Tool Pair Safety**:
  - **Modular Architecture**: Refactored monolithic `summarizer.py` (600+ lines) into a clean modular structure in `src/zrb/llm/summarizer/` with separate modules for chunk processing, history splitting, message conversion, message processing, and text summarization.
  - **Tool Pair Integrity**: Enhanced history splitting logic to NEVER break complete tool call/return pairs (Pydantic AI requirement). Added `validate_tool_pair_integrity()` function to detect and warn about broken tool pairs.
  - **Best-Effort Splitting**: When no perfect split exists, the system now uses a best-effort approach that minimizes damage while respecting Pydantic AI constraints.
  - **Increased Default Window**: Raised default `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW` from 30 to 100 messages for better context preservation.

## 2.2.12

- **Bug Fix: Corrupted Mandate Restoration**:
  - **Mandate.md Corruption Fix**: Restored missing content in `src/zrb/llm/prompt/markdown/mandate.md` that was corrupted by placeholder text ("...") in commit c8e077e6 ("Add feature/fix bug").
  - **Complete Section Restoration**: Recovered detailed thought block instructions and systematic workflow guidance from tag 2.2.9, merging them with improved delegation rules and examples from the current version.

## 2.2.11

- **Improvement: Thinking Tag Removal & Summarizer Robustness**:
  - **Robust Thinking Tag Removal**: Enhanced the thinking tag removal logic in `llm_task.py` to strip ANSI escape codes before removing `<thinking>` tags, ensuring reliable cleanup of internal reasoning blocks from agent responses.
  - **Summarizer Default Value Fix**: Added proper default value assignment for `summary_window` parameter in `summarizer.py`, preventing potential `None` value errors and improving stability of history summarization.
  - **Default Summarization Windows**: Change default summarization from 12 to 30

## 2.2.10

- **Improvement: Summarization & History Processing**:
  - **Robust Summarizer**: Major refactoring of the history summarization logic to improve stability and context retention.
  - **Stream Response Handling**: Enhanced handling of streaming responses during summarization to prevent interruptions.

- **Improvement: UI/UX & Visualization**:
  - **Enhanced Tool Visualization**: Improved the visual presentation of file operations (`write_file`, `replace_in_file`) in the chat interface, making code changes easier to review.
  - **Completion Rendering**: Refined the completion rendering logic in `completion.py` for a smoother user experience.
  - **Prompt Tweaks**: Minor updates to core prompts and mandates to align with visual improvements.

## 2.2.9

- **Feature: Enhanced Two-Tier Summarization System**:
  - **Conversational Summarizer**: Introduced a specialized agent for distilling entire conversation history into structured XML `<state_snapshot>` format, preserving critical context while dramatically reducing token usage.
  - **Message Summarizer**: Added a dedicated agent for summarizing individual large tool call results and messages, preventing token overflow from verbose tool outputs.
  - **Structured State Snapshots**: Implemented comprehensive XML-based state tracking with sections for goals, constraints, knowledge, reasoning summaries, artifact trails, and task states.

- **Improvement: Configuration Refinement**:
  - **Token Property Standardization**: Renamed token-related configuration properties from plural to singular for consistency (`LLM_MAX_TOKENS_PER_MINUTE` → `LLM_MAX_TOKEN_PER_MINUTE`, `LLM_MAX_TOKENS_PER_REQUEST` → `LLM_MAX_TOKEN_PER_REQUEST`).
  - **Granular Summarization Thresholds**: Added separate configuration options for conversational summarization (`LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`) and message summarization (`LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD`).
  - **Increased History Window**: Raised default history summarization window from 5 to 12 messages for better context preservation.

- **Improvement: History Processing & Stability**:
  - **Emergency Failsafe**: Added robust handling for cases where summarization fails to reduce history size below API limits, with automatic pruning to prevent crashes.
  - **Smart Message Merging**: Implemented safety checks to merge consecutive `ModelRequest` messages when appropriate, improving conversation flow.
  - **Enhanced Chunking Logic**: Added intelligent text chunking for extremely large tool results, ensuring reliable summarization of massive outputs.

- **Security & Reliability**:
  - **Prompt Injection Defense**: Added explicit security rules to summarizer prompts to ignore adversarial content and formatting instructions within chat history.
  - **Token Budget Enforcement**: Implemented strict token budget constraints for state snapshots (target <2000 tokens) to prevent system loops.
  - **Backward Compatibility**: Maintained support for legacy environment variable names while preferring new standardized forms.

## 2.2.8

- **Improvement: Enhanced Agent Reasoning & Planning**:
  - **Structured Thought Process**: Added mandatory `<thought>...</thought>` tags for internal reasoning before every response and tool call, improving transparency and decision-making quality.
  - **Systematic Workflow Refinement**: Enhanced the DEEP PATH workflow with explicit RESEARCH, STRATEGY, EXECUTION, and FINALITY phases for complex tasks.
  - **Bug Fix Methodology**: Added requirement to empirically reproduce failures with tests or scripts before applying fixes.

- **Improvement: Core Prompt Refinements**:
  - **Mandate Restructuring**: Reorganized mandate into logical sections: Internal Reasoning & Planning, Systematic Workflow, Communication & Delegation, Maintenance & Errors, and Context & Safety.
  - **Persona Enhancement**: Updated Senior Staff Engineer persona to prioritize maintainability over cleverness and always look for the "Standard Way" before inventing new solutions.
  - **Summarizer Enhancement**: Added `<reasoning_summary>` section to capture key logical deductions and architectural decisions from thought blocks.

- **Improvement: Operational Attitude**:
  - **Logical & Proactive Approach**: Added emphasis on thinking through architecture, identifying edge cases, and potential regressions before implementation.
  - **Security Emphasis**: Added explicit protection for `.env` and `.git` folders in security guidelines.
  - **Error Recovery**: Enhanced error handling with backtracking to Research or Strategy phase when a path fails.

## 2.2.7

- **Feature: Comprehensive Skill System**:
  - **Specialized Skill Definitions**: Added comprehensive skill definitions for common workflows including `commit`, `debug`, `init`, `plan`, `pr`, `research`, `review`, `skill-creator`, and `test`.
  - **Structured Workflows**: Each skill provides detailed, step-by-step guidance for executing specific tasks with proper verification and quality standards.
  - **User-Invocable Commands**: Skills are configured as user-invocable slash commands for direct access in the chat interface.

- **Improvement: Agent Delegation Protocol**:
  - **Enhanced Context Requirements**: Updated delegate tool documentation to emphasize that sub-agents are blank slates requiring full context (file contents, architectural details, environment info).
  - **Clearer Instructions**: Added explicit guidance for providing highly specific instructions when delegating to sub-agents.
  - **Mandate Alignment**: Updated core mandate to reflect the improved delegation protocol.

- **Refinement: Agent Definitions**:
  - **Coder Agent Enhancement**: Redefined as "Senior Software Engineer" with focus on code quality, safety, and rigorous verification. Added explicit "Read Before Writing" directive and improved Edit-Test-Fix loop guidance.
  - **Planner Agent Enhancement**: Redefined as "Systems Architect" with improved discovery phase guidance, risk analysis, and structured roadmap communication.
  - **Researcher & Reviewer Updates**: Enhanced agent descriptions and directives for better clarity and effectiveness.

- **Improvement: Documentation & Configuration**:
  - **LLM Integration Docs**: Updated configuration documentation for better clarity on LLM integration and rate limiting.
  - **Minor UI Tweaks**: Small improvements to TUI interface for better user experience.

## 2.2.6

- **Refactor: LLM Tool Standardization**:
  - **PascalCase Tool Names**: Renamed all LLM tools to use PascalCase aliases matching Claude standard conventions (e.g., `read_file` → `Read`, `write_file` → `Write`, `replace_in_file` → `Edit`).
  - **Tool Registry Cleanup**: Removed aliases and custom names from LLM tool registry, simplifying tool loading logic and improving consistency.
  - **Claude Compatibility**: Updated tool names to match Claude Code conventions for better interoperability.

- **Improvement: Core Documentation Restructuring**:
  - **Mandate Reorganization**: Completely restructured `mandate.md` with clearer organization into Context & Safety, Systematic Workflow, Communication & Delegation, and Maintenance & Errors sections.
  - **AGENTS.md Simplification**: Streamlined the agent guide to focus on practical development conventions and directory navigation.
  - **Enhanced Readability**: Improved documentation structure for better clarity and maintainability.

- **Dependency Management**:
  - **Termux Compatibility**: Limited `griffe` dependency to version < 2.0 for Termux compatibility, ensuring broader platform support.
  - **Dependency Updates**: Updated poetry.lock with refreshed dependency resolutions.

- **Configuration Updates**:
  - **Tool Policy Alignment**: Updated tool policies to match new PascalCase tool names.
  - **Agent Definition Updates**: Revised agent definitions to reference updated tool names and conventions.

## 2.2.5

- **Feature: Extended LLM Provider Support**:
  - **xAI Integration**: Added native support for xAI models via the new `xai` extra, providing access to Grok models through the official `xai-sdk`.
  - **Voyage AI Integration**: Added comprehensive support for Voyage AI embeddings and RAG capabilities via the new `voyageai` extra, including automatic dependency management.
  - **Dependency Updates**: Upgraded `pydantic-ai-slim` to `1.57.0` and `anthropic` to `>=0.78.0` for latest features and stability.
  - **Python Version Support**: Updated Python constraint to `<3.14.0` for forward compatibility.

- **Improvement: TUI Stability & Concurrency**:
  - **Message Queue System**: Implemented a robust job queue (`_message_queue`) to prevent overlapping AI responses and shell command execution, eliminating race conditions.
  - **Sequential Processing**: Ensures only one LLM task or shell command runs at a time, improving UI responsiveness and preventing state corruption.
  - **Better Trigger Handling**: Enhanced async iterator handling for external triggers with proper error isolation.

- **Improvement: Configuration & Performance**:
  - **Increased Token Limits**: Raised default `LLM_MAX_TOKENS_PER_MINUTE` from 120,000 to 128,000 to better accommodate modern model contexts.
  - **Extended Provider Configuration**: Added environment variable support for xAI and Voyage AI API keys and base URLs.

- **Refinement: Core Prompts & Agent Behavior**:
  - **Enhanced Persona**: Redefined as a "Polymath AI Assistant" with fluid expertise, adapting to coding (Senior Staff Engineer), writing (Creative Author), and research (Rigorous Analyst) contexts.
  - **Mandate Precision**: Added explicit style mimicry guidelines for both code (indentation, naming) and prose (tone, formatting).
  - **Knowledge Stewardship**: Mandated proactive use of note tools (`write_contextual_note`, `write_long_term_note`) to preserve learned patterns and preferences.
  - **Planning Rigor**: Expanded implementation guidance with context precision, import safety, and proofreading requirements.

- **Bug Fixes & Maintenance**:
  - **UI Cleanup**: Fixed resource cleanup on exit, properly cancelling message processor and ensuring queue drainage.
  - **Trigger Reliability**: Improved error handling in trigger loops to prevent cascading failures.
  - **Dependency Alignment**: Synchronized extras markers across `poetry.lock` for consistent optional dependency resolution.

## 2.2.4

- **Feature: Robust Hook System**:
  - **Claude Compatibility**: Full support for Claude Code-style declarative hooks with 100% event parity.
  - **Thread-Safe Execution**: Implemented a dedicated `HookExecutor` with built-in thread-safety and configurable timeouts for background operations.
  - **Advanced Matchers**: Added support for complex hook filtering using field matchers with multiple operators (regex, glob, contains, etc.).
  - **Expanded Hook Types**: Support for `Command`, `Prompt`, and `Agent` hooks with automatic environment injection.
  - **Comprehensive Documentation**: Added new guides for [Hook System](./hook-system.md) and [Quick Start](./hook-quickstart.md).
- **Improvement: TUI & UX Refinement**:
  - **Fluid Input**: The chat interface now supports empty inputs and better multi-line handling.
  - **Dynamic Keybindings**: Improved keybinding management and added new shortcuts for session control.
  - **Visual Stability**: Refined the main layout and UI components to prevent flickering and improve responsiveness.
- **Improvement: Agent Intelligence**:
  - **Context-Aware Summarization**: Optimized the history summarization agent to better preserve critical session details while reducing token usage.
  - **Extensible Tooling**: Enhanced the tool registry and delegate tool system to support more complex multi-agent workflows.
- **Bug Fixes**:
  - **Hook Reliability**: Resolved thread-safety issues in hook execution that previously caused intermittent TUI hangs.
  - **Summarization Fixes**: Corrected an issue where the summarization agent would occasionally lose context in long sessions.
  - **Claude Compatibility**: Fixed several edge cases in the Claude hook compatibility layer.

## 2.2.3

- **Bug Fix: TUI Broken Pipe**: Resolved a critical regression where asynchronous hook calls from background threads (e.g., stream capture) would crash the UI and cause `Broken pipe` errors.
- **Improvement: Trigger Visibility**: Added explicit error reporting and validation for external triggers (e.g., voice listen), ensuring that failures are no longer silently swallowed.

## 2.2.2

- **Feature: Dynamic Input Field**: The chat input area now dynamically adjusts its height based on the content (up to 10 lines), improving visibility for multi-line messages.
- **Improvement: TUI Layout Optimization**:
  - Redesigned the main interface to remove redundant framing around history, maximizing vertical space.
  - Enhanced scrolling logic to ensure the latest conversation markers are always correctly positioned.
  - Improved visual spacing and structural padding across the Title Bar, Info Bar, and Status Bar for a more modern, polished feel.

## 2.2.1

- **Bug Fix: ToolDenied Attribute Error**: Fixed an issue where the agent incorrectly attempted to access a non-existent `reason` property on `pydantic_ai.ToolDenied` objects. It now correctly uses the `message` attribute when executing `PostToolUseFailure` hooks.

## 2.2.0

- **Feature: Extensible Hook System**:
  - **Comprehensive Lifecycle Integration**: Implemented a robust hook system in `zrb.llm.hook` executing at all major agent and UI lifecycle points: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PreCompact`, `SessionEnd`, `Notification`, and `Stop`.
  - **Claude Code Compatibility**: Native support for Claude Code-style declarative hooks (JSON/YAML) with automatic "hydration" into Python callables. Hooks are discovered from both `.claude/` and `.{ROOT_GROUP_NAME}/` directories.
  - **Python-Native Hooks**: Users can register arbitrary async Python functions as hooks directly via `hook_manager.register()`.
  - **Hook Management**: Centralized `HookManager` with automatic configuration loading, directory scanning, and prioritized execution.
  - **Tool Manipulation**: `PreToolUse` hooks can dynamically modify tool arguments or cancel execution entirely.

- **Improvement: Claude Code Ecosystem Compatibility**:
  - **Consolidated Documentation**: Added a new [Claude Code Compatibility](./advanced-topics/claude-compatibility.md) guide detailing Zrb's support for Claude-style Skills, Agents, Subagents, Hooks, and Project Instructions.
  - **Expanded Discovery**: Standardized search paths across Skills, Agents, and Hooks to respect both `.claude` and Zrb-specific configuration folders.

- **Improvement: TUI Responsiveness & Visual Stability**:
  - **Artifact-Free Rendering**: Implemented a background `_refresh_loop` and manual line centering with full-width padding in `ui.py` to eliminate rendering artifacts and "ghost" characters in the TUI header.
  - **Performance Optimization**: Reduced the `prompt_toolkit` refresh interval to `0.05s` for a significantly smoother user experience.
  - **UI Resiliency**: Improved error handling and state management within the TUI to prevent displacement during dynamic content updates.

- **Refactor: Logic Simplification & DRY Compliance**:
  - **Shared Utility Centralization**: Extracted duplicated path exclusion logic into a unified `is_path_excluded` utility in `zrb.util.file`, simplifying `list_files`, `glob_files`, and `analyze_code` tools.
  - **Todo Logic Optimization**: Refactored `select_todo_task` to remove redundant loop structures, improving code readability and performance.
  - **Architectural Standardization**: Updated `AGENTS.md` with "LLM Extension Architectural Patterns" to ensure consistent use of classic Python classes and module-level singletons.

- **Maintenance**:
  - **New Test Suite**: Added comprehensive test coverage for the hook system (`test/llm/hook/`).
  - **Configuration Expansion**: Added `ZRB_HOOKS_ENABLED`, `ZRB_HOOKS_DIRS`, `ZRB_HOOKS_TIMEOUT`, and `ZRB_HOOKS_LOG_LEVEL` environment variables.

## 2.1.0

- **Feature: Small Model Configuration**:
  - **LLM_SMALL_MODEL Support**: Added new configuration option `ZRB_LLM_SMALL_MODEL` for specifying a smaller/faster model for summarization and other auxiliary tasks. The `small_model` property is now available in `LLMConfig`.
  - **Enhanced Fuzzy Matching**: Improved fuzzy matching algorithm with boundary bonuses and subsequence penalties for better file path matching in autocompletion.
  
- **Improvement: Model Resolution & Provider Handling**:
  - **Built-in Provider Support**: Updated model resolution logic to properly handle built-in providers (DeepSeek, Ollama, Anthropic, Google, Groq, Mistral) without incorrectly transforming them to use OpenAI provider prefix.
  - **Summarizer Optimization**: Updated summarizer agent to automatically use `small_model` when no specific model is provided, improving efficiency for summarization tasks.
  
- **Bug Fix: Model Display Correction**:
  - **DeepSeek/Ollama Display**: Fixed issue where DeepSeek and Ollama models were incorrectly displayed with `openai:` prefix in the UI when `ZRB_LLM_MODEL` was set to `deepseek:model-name` or `ollama:model-name`.
  
- **Maintenance: Testing & Documentation**:
  - **Configuration Tests**: Added comprehensive tests for new `LLM_SMALL_MODEL` and `LLM_PLUGIN_DIRS` configuration options.
  - **Fuzzy Match Tests**: Added tests for improved fuzzy matching algorithm to ensure proper path matching behavior.

- **Breaking Changes**:
  - **Plugin Directory Configuration**: The environment variable `ZRB_LLM_PLUGIN_DIR` has been renamed to `ZRB_LLM_PLUGIN_DIRS` (plural). Users with custom plugin directories need to update their configuration.

## 2.0.19

- **Feature: Active Skills Support in LLM Tasks**:
  - **PromptManager Update**: Added `active_skills` (`StrListAttr`) and `render_active_skills` parameters to `PromptManager` for better control over which skills are loaded into the system prompt.
  - **LLMTask & LLMChatTask Update**: Added `active_skills` and `render_active_skills` parameters. These tasks now automatically instantiate a `PromptManager` if these parameters are provided, simplifying task configuration.
  - **Dynamic Resolution**: `PromptManager` now dynamically resolves `active_skills` from the context during prompt composition, allowing for conditional or dynamic pre-loading of skill content.

## 2.0.18

- **Feature: Sub-Agent Detection & Delegation**:
  - **Enhanced Delegation**: Implemented a robust `delegate_to_agent` tool and logic in `AgentManager` to improve how the main agent hands off tasks to specialized sub-agents.
  - **Smart Detection**: improved logic to detect when a sub-agent should be invoked based on task complexity or specificity.
- **Refactor: Agent & Prompt Organization**:
  - **Plugin-Based Agents**: Moved built-in agent definitions (Coder, Planner, Researcher, Reviewer) from general prompt directories to a dedicated `src/zrb/llm_plugin/agents/` structure, treating them more like plugins.
  - **Prompt Manager Updates**: Refactored `PromptManager` to align with the new agent plugin structure.
- **Refinement: Core Prompts & Mandates**:
  - **Strict Verification**: Updated `mandate.md` to explicitly require checks for keywords, structure, and citations in text and research tasks.
  - **Loop Prevention**: Added explicit loop prevention and stop condition directives to the `Coder` agent to reduce redundant tool calls.
  - **Planning Rigor**: Updated the `Planner` agent to explicitly list required artifacts, keywords, and format constraints during the requirements phase.
  - **Research Standards**: Mandated the inclusion of a "References" section for the `Researcher` agent.
- **Improvement: LLM Challenges**:
  - **Updated Benchmarks**: Refreshed runner scripts and experiment results to reflect the improved agent behaviors.

## 2.0.17

- **Feature: Enhanced Prompt Management & Active Skills**:
  - **Active Skills Support**: Added `active_skills` parameter to `PromptManager` and `create_claude_skills_prompt` to allow pre-loading skill content directly into system prompts.
  - **Project Context Separation**: Split `create_claude_skills_prompt` into two functions: `create_claude_skills_prompt` (skill management) and `create_project_context_prompt` (CLAUDE.md/AGENTS.md loading).
  - **Configurable Project Context**: Added `include_project_context` parameter to `PromptManager` to control whether project documentation is included.
- **Improvement: Tool Safety Wrapper Centralization**:
  - **Moved Safety Logic**: Consolidated tool error handling from `LLMTask` into `create_agent` function in `common.py` for consistent safety across all agent usage.
  - **Robust Error Handling**: Tools and toolsets are now automatically wrapped with error handling to prevent agent crashes from faulty tool calls.
- **Refinement: Core Prompts & Code Quality**:
  - **Updated Mandate**: Refined communication protocol in `mandate.md` for clearer guidance on when to be concise vs. provide detailed explanations.
  - **Import Cleanup**: Streamlined import statements in `llm_chat_task.py` and `llm_task.py` for better code organization.
  - **Type Hint Improvements**: Enhanced type annotations throughout the prompt management system.

## 2.0.16

- **Fix: Fix Zrb skill directory path**: The Zrb skill directory path is now `~/.zrb/skills`

## 2.0.15

- **Fix: LLM Configuration & Task Handling**:
  - **Empty Model Name Handling**: Fixed an issue in `LLMChatTask` and `LLMTask` where empty string model names were not correctly treated as `None`, potentially causing model resolution failures.
- **Feature: LLM Chat Enhancements**:
  - **Model Input Support**: The built-in `llm_chat` task now accepts a `model` input argument, allowing for dynamic model selection during task execution.
- **Refinement: Runner & Documentation**:
  - **Model Naming Convention**: Updated `llm-challenges` runner script and documentation to support and encourage specific model naming (e.g., `google-gla:gemini-2.5-flash`) for better clarity and compatibility.
  - **Updated Dependencies**: Bumped version to `2.0.15`.

## 2.0.14

- **Fix: LLM Configuration & Custom Provider Support**:
  - **Model Resolution**: Fixed a bug where custom `Model` objects (e.g., for DeepSeek or OpenAI-compatible proxies) were being stringified when passed to sub-tasks, causing "Unknown model" errors.
  - **Provider Intelligence**: Enhanced `LLMConfig` to intelligently resolve providers based on model names, ensuring custom `base_url` and `api_key` are correctly applied to OpenAI-compatible models while maintaining compatibility with native providers like Anthropic and Google.
- **Fix: Robustness & Stability**:
  - **Serialization Safety**: Implemented input sanitization in `Session.as_state_log()` to prevent `PydanticSerializationError` when task inputs contain non-serializable objects (like LLM clients or models).
  - **CLI Entry Point**: Added a proper `if __name__ == "__main__":` block to `src/zrb/__main__.py` to ensure the CLI executes correctly when run as a module via `python -m zrb`.

## 2.0.13

- **Feature: Dynamic YOLO & Model Switching**:
  - **Runtime YOLO Toggle**: Added ability to toggle "YOLO mode" (skipping tool approval) dynamically while the agent is running using `/yolo` or `Ctrl+Y`.
  - **Model Switching**: Introduced `/model <name>` command to switch LLM models on the fly.
  - **Enhanced Autocompletion**: Implemented VS Code-style fuzzy completion for commands and model names, including a programmatically generated list of supported models from `pydantic-ai`.
- **Improvement: Robustness & Safety**:
  - **Safe Toolset Execution**: Wrapped `AbstractToolset` execution to catch and report errors gracefully to the LLM, preventing agent crashes from faulty tool calls.
  - **Expanded Skill Discovery**: Updated `SkillManager` to look for skills in `.zrb/skill` (or configured root group name) in addition to the standard `.claude/skills` directory.
- **Refinement: Core Logic**:
  - **Prompt Manager**: Enhanced `PromptManager` to accept raw strings as prompts, automatically wrapping them with context rendering logic.
  - **XCom Usage**: Refined `LLMChatTask` and `UI` to use `Xcom` objects for shared state management (YOLO mode), ensuring proper synchronization.
  - **Prompt Accuracy**: Merged improvements for better prompt accuracy and challenge handling.

## 2.0.12

- **Feature: LLM Challenge Suite**: Added a comprehensive suite of challenges in `llm-challenges/` for benchmarking AI agent performance in scenarios like bug fixing, refactoring, and copywriting.
- **Refinement: Core Prompts**:
  - **Updated Mandate & Persona**: Refined `mandate.md` and `persona.md` to ensure better alignment with the agent's operating directives and persona.
  - **Renamed Compatibility Module**: Renamed `claude_compatibility.py` to `claude.py` for better clarity.
- **Documentation**:
  - **Updated Agent Guide**: Comprehensive update to `AGENTS.md` to provide clearer context and guidelines for LLMs working with the Zrb project.
- **Remove CI_TOOLS argument from Dockerfile**

## 2.0.11

- **Fix: Exclude `.claude` directory from code analysis**

## 2.0.10

- **Feature: Structured History Summarization**:
  - **XML State Snapshot**: Overhauled the summarizer prompt to generate structured `<state_snapshot>` XML (Goals, Constraints, Knowledge, Artifacts, Tasks) instead of unstructured text, improving the agent's long-term memory and context retention.
  - **Iterative Chunking**: Implemented smart history splitting to process large conversations in manageable chunks, preventing context window overflows.
  - **Recursive Compression**: Added logic to recursively re-summarize content if the aggregated summary remains too large.
- **Improvement: Rate Limiting & Safety**:
  - **Token-Aware Truncation**: Added `truncate_text` to `LLMLimiter` with `tiktoken` support (and fallback) to safely handle massive message blocks during summarization.
  - **Prompt Injection Defense**: Added explicit security rules to the summarizer system prompt to ignore adversarial content within the chat history.
- **Refinement: Core Prompts**:
  - **Mandate & Persona**: Polished `mandate.md` and `persona.md` for better clarity and stricter adherence to safety and convention guidelines.
- **Maintenance**:
  - Updated dependencies (`poetry.lock`, `pyproject.toml`).

## 2.0.9

- **Fix: CFG.LLM_ASSISTANT_NAME lazy load**

## 2.0.8

- **Fix: Art resolution** Fixing art resolution in case of user provided the file

## 2.0.7

- **Update: ASCII Art Collection**:
  - Added new ASCII art files: `batman.txt`, `butterfly.txt`, `clover.txt`, `hello-kitty.txt`, and `star.txt` under `src/zrb/util/ascii_art/art/`.
  - Updated banner ASCII art format in `src/zrb/util/ascii_art/banner.py`.
  
- **Enhancement: LLM Prompt Management**:
  - Added new markdown-based prompts for various roles such as `executor`, `orchestrator`, `planner`, `researcher`, and `reviewer` under `src/zrb/llm/prompt/markdown/`.

- **Improvement: LLM Configuration**:
  - Reviewed and possibly updated configurations related to LLM management in `src/zrb/config/config.py`.
  - The default configuration for web components and token thresholds is now more flexible.
  
- **Minor Fixes & Adjustments**:
  - Increased readability of the `Config` class with comprehensive property management.
  - `src/zrb/builtin/llm/chat.py` adapted to improve task and tool management for LLM operations.

## 2.0.6

- **Feature: Hierarchical Prompt Configuration**:
  - **Recursive Prompt Discovery**: Updated `get_default_prompt` to traverse up the directory tree (up to the home directory) when searching for custom prompt overrides.
  - **Improved Search Logic**: Implemented `_get_default_prompt_search_path` to intelligently identify search paths only when the current directory is within the home directory.
- **Improvement: LLM History Management**:
  - **Lazy Initialization Fix**: Refactored `LLMTask` and `LLMChatTask` to ensure `FileHistoryManager` is properly initialized before use, preventing potential `AttributeError`.
- **Bug Fixes & Refinements**:
  - **Fixed Test Integration**: Updated `test_tool_policy_integration.py` to ensure `test_print` accepts arbitrary keyword arguments, maintaining compatibility with internal streaming response utilities.
- **Testing**:
  - **New Prompt Traversal Tests**: Added comprehensive unit tests in `test/llm/prompt/test_default_prompt.py` to validate hierarchical prompt discovery.
  - **Updated Task Tests**: Enhanced `test/llm/task/test_llm_task_tool_confirmation.py` with mock history managers to ensure stability.

## 2.0.5

- **Feature: Enhanced Context Management**:
  - **Global ContextVar System**: Introduced `current_ctx` ContextVar and `zrb_print()` function for consistent, context-aware printing throughout the codebase.
  - **Task Execution Context**: Added proper context management to task execution, ensuring context variables are properly set and reset during task runs.
  - **Tool Factory Support**: Added `tool_factories` and `toolset_factories` parameters to `LLMChatTask`, enabling dynamic tool resolution based on runtime context.
- **Improvement: Configuration Consistency**:
  - **Standardized Config Property Names**: Updated `LLM_MAX_REQUESTS_PER_MINUTE` to `LLM_MAX_REQUEST_PER_MINUTE` (singular) for consistency with other config properties.
  - **Backward Compatibility**: Maintained support for old environment variable names (`LLM_MAX_REQUESTS_PER_MINUTE`) while preferring the new singular form.
- **Improvement: Rate Limiting & Token Management**:
  - **Enhanced Token Counting**: Improved token estimation with better fallback approximation (char/3 instead of char/4) and 95% buffer for context window management.
  - **Better Rate Limit Notifications**: Added cyan styling to rate limit messages and improved notification clearing mechanism.
  - **Smarter Throttling**: Enhanced `_can_proceed()` logic to handle empty logs more gracefully.
- **Improvement: UI/UX Enhancements**:
  - **Consistent Styling**: Applied `stylize_faint()` and `stylize_error()` to UI messages for better visual hierarchy.
  - **Improved Command Display**: Streamlined command output formatting with timestamps inline.
  - **Better Error Feedback**: Enhanced error messages with proper styling throughout the TUI.
- **Improvement: History & Conversation Management**:
  - **Summarization Feedback**: Added progress notifications when compressing conversations due to token threshold limits.
  - **Consistent Printing**: Updated `FileHistoryManager` to use `zrb_print()` for consistent error/warning messages.
- **Bug Fixes & Refinements**:
  - **Fixed Tool Name Assignment**: Removed explicit `__name__` assignment from note tools as pydantic-ai handles this automatically.
  - **Improved Tool Resolution**: Enhanced `LLMChatTask` to properly resolve tools from factories during execution.
  - **Better Async Context Management**: Added proper async context stack management for toolsets with `__aenter__` support.
  - **Fixed Test Compatibility**: Updated tests to pass context to `_create_llm_task_core()` method.
- **Code Quality**:
  - **Consistent Printing**: Replaced direct `print()` calls with `zrb_print()` throughout LLM tools (bash, code, mcp, rag, note).
  - **Prompt Manager Reset**: Added `reset()` method to `PromptManager` for easier testing and reinitialization.
  - **Type Safety**: Cleaned up imports and type annotations in agent common module.

## 2.0.3

- **Feature: Context-Aware LLM Agent Execution**:
  - **UI & Tool Confirmation Inheritance**: Introduced `ContextVar`-based context management for UI and tool confirmation settings, allowing sub-agents to automatically inherit parent agent configurations.
  - **Improved Event Handling**: Enhanced streaming response management with better UI integration and configurable event handlers.
  - **Enhanced Rate Limiting**: Updated rate limiter to accept message/history context for more accurate token estimation and throttling.
- **Improvement: Skill Command System**:
  - **Fixed Skill Command Factory**: Resolved function signature issue by removing unnecessary splat operator and implementing proper factory pattern for dynamic skill command loading.
  - **Enhanced Custom Command Resolution**: Improved LLM chat task to support both direct commands and factory functions for custom command registration.
- **Improvement: History Summarization**:
  - **Better Message Representation**: Added `message_to_text()` function to convert pydantic_ai messages into readable text for more accurate history summarization.
  - **Default Summarizer**: LLM chat tasks now automatically include a summarizer history processor by default to manage long conversation histories.
- **Bug Fixes & Refinements**:
  - **Fixed Faint Printer**: Corrected `create_faint_printer()` to accept a print function instead of context, resolving compatibility issues with streaming responses.
  - **Improved Argument Extraction**: Fixed typo in `_extract_args()` function parameter name for consistency.
  - **Enhanced Sub-Agent Tool**: Updated sub-agent tool to leverage automatic UI and tool confirmation inheritance via context variables.
- **Code Quality**:
  - **Clean Architecture**: Improved separation of concerns in agent execution with proper context management and cleanup.
  - **Type Safety**: Enhanced type annotations and error handling throughout the LLM module.

## 2.0.2

- **Improvement: Enhanced Skill Management**:
  - **Depth-Controlled Scanning**: Added `max_depth` parameter to `SkillManager` to control recursive directory scanning depth, improving performance for large projects.
  - **Customizable Ignore Patterns**: Introduced `ignore_dirs` parameter allowing users to customize which directories to skip during skill discovery.
  - **Refined Directory Ignore List**: Updated default ignore patterns to be more focused on build artifacts and less on IDE-specific directories.
  - **Improved Error Handling**: Added robust try-catch blocks to gracefully handle permission errors and inaccessible directories during skill scanning.
- **Code Quality & Maintenance**:
  - **Cleanup**: Removed unused import (`ToolCallHandler`) from `llm_chat_task.py` to reduce code clutter.
  - **Naming Consistency**: Refactored `IGNORE_DIRS` constant to `_IGNORE_DIRS` following Python convention for module-private variables.
- **Testing**:
  - **Comprehensive Depth Testing**: Added thorough unit tests for the new `max_depth` functionality, ensuring skill discovery respects depth limits.
  - **Edge Case Coverage**: Enhanced test suite to validate skill manager behavior with deeply nested directory structures.

## 2.0.1

- **Feature: Enhanced LLM Interaction**:
  - **Slash Commands for Skills**: Automatically converted user-invocable Claude skills into executable slash commands (e.g., `/<skill-name>`) within the chat TUI.
  - **Dynamic Argument Extraction**: Implemented automatic argument detection and parsing for skill-based slash commands.
  - **Safer Tool Policies**: Improved `auto_approve` tool policy with directory-aware checks, automatically approving read operations only within the current working directory.
- **Improvement: LLM Prompt & Mandate**:
  - **Assertive Mandate**: Updated the core mandate to be more assertive, explicitly requiring the AI to check the provided system context before using discovery tools.
  - **Streamlined System Context**: Flattened the system context structure to remove redundant headers and improve token efficiency.
  - **Anti-Hallucination Measures**: Added explicit instructions to prevent the AI from defaulting to "You are absolutely right" and instead focus on reasoned explanations.
- **Documentation**:
  - **New Guide**: Added [Customizing the AI Assistant](./advanced-topics/customizing-ai-assistant.md) guide.
  - **Updated Docs**: Comprehensive updates to task type documentation, configuration guides, and architectural overviews to match the 2.0 architecture.
- **Bug Fixes & Refinement**:
  - Fixed argument residue handling in custom chat commands.
  - Improved autocompletion metadata for custom commands in the TUI.
  - Refined skill management to distinguish between model-invocable and user-invocable skills.

## 2.0.0

- **Refactor: Major Architectural Overhaul**:
  - **LLM Module Consolidation**: Moved all LLM-related logic from `src/zrb/builtin/llm` and `src/zrb/task/llm` to a unified `src/zrb/llm` package for better modularity and maintainability.
  - **Tool Relocation**: LLM tools (e.g., `analyze_repo`, `write_to_file`) are now located in `zrb.llm.tool`.
  - **Centralized Configuration**: Merged multiple LLM-specific and project-wide configuration files into a robust, centralized `Config` class in `src/zrb/config/config.py`.
- **Feature: Enhanced LLM Interface**:
  - **Interactive TUI**: Introduced a new, feature-rich Terminal User Interface (TUI) for `llm-chat`, providing a more responsive and visually appealing experience with syntax highlighting and custom layouts.
  - **Improved Command Structure**: Consolidated and refined LLM-related commands (e.g., `/save`, `/load`, `/attach`, `/exec`) for better usability.
  - **ASCII Art & Banners**: Added customizable ASCII art and banners for the CLI and AI assistant.
- **Feature: Prompt & Agent Management**:
  - **Centralized Prompt System**: Introduced a more robust prompt management system with support for markdown-based templates.
  - **Skill Management**: Introduced a new skill management system to extend LLM capabilities dynamically via `SkillManager`.
  - **New Agent Framework**: Re-implemented LLM agents with better history tracking, summarization, and tool-call policies.
- **Feature: LLM Challenge Suite**:
  - **Benchmarking**: Added a comprehensive suite of challenges in `llm-challenges/` for benchmarking AI agent performance in scenarios like bug fixing, refactoring, and copywriting.
- **Performance & Cleanup**:
  - **Code Pruning**: Conducted a significant "prune" of the codebase, removing redundant components, old tests, and unused dependencies to improve startup time and reduce package size.
  - **Lazy Loading**: Further optimized imports to ensure faster CLI responsiveness.
- **Testing**:
  - **Updated Test Suite**: Completely refactored the test suite to align with the new architecture, ensuring high coverage and stability for the 2.0 release.

🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Changelog v2](README.md)
