🔖 [Documentation Home](../README.md)

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