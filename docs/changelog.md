🔖 [Documentation Home](../README.md)

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

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)