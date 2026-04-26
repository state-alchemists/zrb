🔖 [Documentation Home](../README.md)

## 2.22.7 (April 26, 2026)

- **Refactoring: Config Extract-Mixin**:
  - `Config` class reduced from ~2435 lines to 59 lines by splitting into 12 focused mixin modules under `src/zrb/config/_mixins/`.
  - The thin shell composes all mixins; public access stays flat (`CFG.WEB_HTTP_PORT`, `CFG.LLM_MODEL`) — no external changes needed.
  - New mixins: `foundation.py`, `web.py`, `llm_core.py`, `llm_ui.py`, `llm_limits.py`, `llm_content.py`, `llm_prompt.py`, `llm_search.py`, `rag.py`, `internet_search.py`, `hooks.py`, `task_runtime.py`.

- **Refactoring: HookManager Extract-Mixin**:
  - Extracted `_loader_mixin.py` (filesystem traversal and format parsing) and `matcher.py` from `manager.py`.
  - `HookManager` now focused on registration, execution, and type-specific hook factories.

- **Refactoring: LLMChatTask Extract-Mixin**:
  - Extracted `_chat_builder_mixin.py` (all `set_*`/`add_*`/`append_*`/`prepend_*` methods) and `_chat_runner_mixin.py` (interactive/non-interactive session runners).
  - `llm_chat_task.py` now focused on `__init__` and `_exec_action` orchestration.

- **Refactoring: BaseUI Extract-Mixin**:
  - Extracted `_commands_mixin.py` (slash-command handlers and shell command execution) from `base_ui.py`.

- **Improvement: ContextVar Discoverability**:
  - New `src/zrb/contextvars.py` serves as a centralized index of every `ContextVar` in the runtime.
  - New `runtime_state.py` for agent-run ambient state (UI, YOLO, approval channel).
  - New `ambient_state.py` for tool-scoped ambient state (worktree, session).
  - Each re-exports typed wrappers from their owning modules for discoverability.

- **Improvement: Public API Surface Documentation**:
  - `src/zrb/__init__.py` reorganized with section comments grouping imports by concern.
  - `Config` class now explicitly exported.

- **Improvement: Public Properties on `LLMChatTask`**:
  - Added public `history_manager`, `ui_factories`, `approval_channels`, and `include_default_ui` properties with setters.
  - `chat_session_runner.py` now accesses these through the public API instead of private attributes.

- **Improvement: Public API on `DefaultUI` Mixins**:
  - `ConfirmationMixin`: new `submit_user_answer()` and `cancel_pending_confirmations()` methods.
  - `LifecycleMixin`: extracted `cleanup_background_tasks()` and `handle_first_render()` as public methods.
  - `OutputMixin`: new `output_text` and `output_field_width` properties.

- **Improvement: Public API on `ChatSessionManager`**:
  - Added `history_manager` property, `set_history_manager()`, `has_session()`, and `sessions` property.

- **Improvement: Public `handle_incoming_message()` on `HttpUI`**:
  - Exposed `handle_incoming_message()` as a public method instead of direct `_input_queue` access.

- **Bug Fix: Nil Tool Call Response**:
  - Fixed `_filter_nil_content()` in `run_agent.py` for providers (e.g., DeepSeek via Cloudflare) that reject `null` content when the response contains only tool calls.
  - Empty `TextPart("")` is now inserted before tool call parts to satisfy API contract.
  - Refined `_is_invalid_tool_call_error()`: removed overly broad "invalid" keyword to reduce false positives.

- **Bug Fix: `os.makedirs` Typo in `todo.py`**:
  - Fixed `os.make_dirs` → `os.makedirs` in `archive_todo`; the archive directory was never created, causing a `FileNotFoundError`.

- **Bug Fix: RAG Hash File Error Handling**:
  - `_load_hash_file()` now catches and logs exceptions instead of propagating them, preventing crashes when the hash file is corrupted or unreadable.

- **Bug Fix: YOLO Inheritance Check Simplified**:
  - `make_yolo_inheritance_checker()` now reads `ui.yolo` directly instead of reaching into `ui._ctx.xcom["yolo"]`, removing the fragile private-attribute access.

- **Bug Fix: Mutable Default Arguments in `get_group_subcommands()`**:
  - Fixed `previous_path=[]` and `subcommands=[]` mutable defaults in `src/zrb/util/cli/subcommand.py`; replaced with `None` and proper initialization guards.

- **Tests: Coverage Expansion**:
  - New `test/test_contextvars_index.py`: verifies the context vars index imports correctly.
  - New `test/llm/agent/test_runtime_state.py`: tests for agent runtime state management.
  - New `test/llm/tool/test_ambient_state.py`: tests for tool-scoped ambient state.
  - Extensive new tests for agent run submodules (`deferred_calls`, `error_classifier`, `openai_patch`, `retry_loop`, `runner`), subagent manager, UI mixins, chat session runner, HTTP UI, web routes, LSP server, RAG tool, code tool, file tool, and CLI utilities.

## 2.22.6 (April 25, 2026)

- **Improvement: Granular Journal Config**:
  - New `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` env var controls whether the journal mandate section appears in the system prompt independently of the reminder.
  - New `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` env var controls whether the end-of-session journaling reminder fires.
  - Both default to `ZRB_LLM_INCLUDE_JOURNAL` when unset — fully backwards compatible.
  - `PromptManager` gains a matching `include_journal_mandate` property; `include_journal` kept as an alias.

- **Improvement: Fuzzy Matching in `replace_in_file`**:
  - Tries exact match first, then falls back to trailing-whitespace-tolerant and indentation-flexible fuzzy matching.
  - Fuzzy matches are reported in the success message so callers know normalization occurred.
  - Fixed replacement count reporting when `count != -1` (now reports `min(match_count, count)` instead of total occurrences).

- **Improvement: Bash Tool Enhancements**:
  - Default `timeout` increased from 30 s to 120 s for long-running commands.
  - New actionable `[SYSTEM SUGGESTION]` messages for common failure patterns: port already in use, command not found, Python module not found, connection refused.

- **Improvement: Tool Guidance Refinements**:
  - Clarified `DelegateToAgent` guidance: when-to-use now explicitly mentions `DelegateToAgentsParallel` as the preferred choice for independent concurrent sub-tasks.
  - Clarified `DelegateToAgentsParallel` guidance: concurrency preference and full-context requirement stated more precisely.

- **Feature: Transient Provider Error Retry**:
  - New `_is_retryable_error()` and `_get_retry_wait()` in `run_agent.py` detect transient provider errors (HTTP 429, 5xx) and retry with exponential backoff.
  - Honors `Retry-After` response header when present, caps wait time at configurable `LLM_API_MAX_WAIT` (default: 60s).
  - New `LLM_API_MAX_RETRIES` config (default: 3) controls total retry attempts; set to `1` to disable.
  - Works alongside existing context-length and invalid-tool retry loops — each error type has independent counters.
  - Documented in `docs/configuration/llm-config.md` under retry configuration.

- **Improvement: System Message Consistency and Tool Cleanup**:
  - Normalized all system messages from mixed `[System]`/`[SYSTEM]` to consistent `[SYSTEM]` prefix across `run_agent.py` and `llm_task.py`.
  - Removed unused sync `tool_safe` decorator from `_wrapper.py` (redundant with `_create_safe_wrapper` in `create_agent()`).
  - Passed `request_limit=None` to `run_stream_events` to override pydantic-ai's default 50-request cap on tool-use loops.

- **Maintenance: Dependency Update**:
  - Updated `pydantic-ai-slim` from `~1.85.0` to `~1.86.1`.
  - Added `AbstractCapability` support: new `capabilities` parameter threaded through `LLMTask` → `LLMChatTask` → `create_agent()` for pydantic-ai 1.86.x compatibility.

## 2.22.5 (April 24, 2026)

- **Bug Fix: More Resilient Tool Call Error Handling**:
  - New `_is_invalid_tool_call_error()` in `run_agent.py` detects HTTP 400 errors caused by invalid or unknown tool names.
  - Some model APIs (e.g., Ollama) reject responses referencing unregistered tools with HTTP 400 instead of handling gracefully.
  - On first occurrence, injects a corrective `[SYSTEM]` message asking the model to use only exact available tool names, then retries.
  - One-time retry via `_invalid_tool_retry_done` flag prevents infinite loops.

- **Improvement: Challenge Runner Verification Priority**:
  - Verification result strings (`VERIFICATION_RESULT: EXCELLENT/PASS/FAIL`) now take priority over execution status.
  - Handles models that complete work correctly but exit with non-zero codes due to unrelated framework exceptions.
  - Fallback to exit code only when no `VERIFICATION_RESULT` marker is present.

- **Maintenance: Updated Challenge Results**:
  - Updated `llm-challenges/experiment/` results across all model providers.

## 2.22.4 (April 22, 2026)

- **Security: Dependency Vulnerability Patches**:
  - Updated `pydantic-ai-slim` from `~1.80.0` to `~1.85.0`.
  - Updated `anthropic` from `>=0.80.0` to `>=0.96.0`.
  - Updated `boto3` from `>=1.42.14` to `>=1.42.63`.
  - Added `jinja2` dependency for improved web templating.
  - Added security pins for transitive dependencies:
    - `python-multipart >=0.0.26` (CVE-2026-40347: DoS via crafted multipart/form-data)
    - `langchain-text-splitters >=1.1.2` (GHSA-fv5p-p927-qmxr: SSRF via redirect bypass)
    - `langsmith >=0.7.31` (GHSA-rr7j-v2q5-chgv: Streaming token events bypass output redaction)
  - Updated `voyageai` extra to include new security dependencies.

- **Improvement: Web Frontend Enhancements**:
  - Added `jinja2` templating engine with centralized `get_jinja_env()` function for consistent template rendering.
  - Added local `mermaid.min.js` (3.2MB) for diagram rendering in web UI, removing external CDN dependency.
  - Improved web route templates with better theme switching, layout, and styling.
  - Enhanced chat interface with better CSS and JavaScript organization.
  - Updated all web route handlers to use new Jinja2 environment for template rendering.

- **Improvement: Server Configuration**:
  - Changed server shutdown timeout from hardcoded `SHUTDOWN_TIMEOUT` to configurable `CFG.WEB_SHUTDOWN_TIMEOUT`.
  - Server now uses milliseconds for timeout configuration (consistent with other timeout settings).

- **Maintenance: Dependency Updates**:
  - Updated `poetry.lock` with latest compatible versions.
  - Minor cleanup in web route imports and template loading.

## 2.22.3 (April 20, 2026)

- **Improvement: Session Wiring via ContextVar**:
  - `system_context` middleware now calls `set_current_session()` with `ctx.input.session`, wiring a `ContextVar` that all four todo tools (`WriteTodos`, `GetTodos`, `UpdateTodo`, `ClearTodos`) read automatically.
  - Replaces the broken `threading.local` approach in `get_current_context_session()`. Async contexts now correctly resolve session identity without explicit `session=` arguments.

- **Improvement: Active Worktree Tracking**:
  - `EnterWorktree` now sets an `active_worktree` `ContextVar`; `ExitWorktree` clears it.
  - The active worktree path is injected into every system context (`- Active worktree: <path>`) and delegate messages, reminding the LLM to pass `cwd` to `Bash` and use absolute paths for file tools.
  - `EnterWorktree` now auto-adds `.zrb/worktree/` to the repo's `.gitignore` via `_ensure_gitignore()`.

- **Improvement: Pending Todos in System Context**:
  - Active (pending/in_progress) todos are now rendered into the system prompt every turn, so the LLM never starts blind.
  - Completed and cancelled items are omitted; the section is suppressed entirely when no active todos exist.

- **Improvement: Recent Commits in System Context**:
  - Last 5 git log entries are now shown in system context (`- Recent commits:`), giving the LLM visibility into recent activity without an explicit `Bash` call.

- **Bug Fix: Agent .md File Filtering**:
  - Fixed `SubAgentManager` incorrectly treating any `.md` file as an agent definition. Now only `.md` files directly inside an `agents/` directory (case-insensitive parent check) are recognized as agents.

- **Improvement: Ripgrep Acceleration for File Search**:
  - `search_files` now tries `rg --files-with-matches` first and falls back to Python `os.walk` if `rg` is unavailable.
  - Gracefully handles `rg` errors (exit code 2) and environments without ripgrep installed.

## 2.22.2 (April 19, 2026)

- **Improvement: Bash Tool Guidance Enhancement**:
  - Added "Never use to query state already in System Context (Time, OS, CWD, available tools)" rule to Bash tool guidance.
  - Prevents redundant system queries when information is already available in the system context.

- **Improvement: Journal Reminder Reordering**:
  - Moved "If nothing is worth journaling" before skill guidance in `journal_reminder.md` for better logical flow.
  - Improves clarity when deciding whether to journal.

- **Improvement: Mandate Simplification**:
  - Consolidated 5-step pre-task clarity into 3 steps in `mandate.md`.
  - Removed redundant "Context Before Action" section.
  - Streamlined guidance for better readability and focus.

## 2.22.1 (April 18, 2026)

- **Improvement: Skill Activation Returns Companion Files**:
  - `ActivateSkill` tool now returns the skill's directory path and companion file listing alongside the skill content.
  - New `_get_companion_files()` helper identifies companion files for skills in dedicated directories (`SKILL.md`/`SKILL.py`).
  - Available Skills section in Claude prompt now mentions companion files.

- **Improvement: System Context Detection Expanded**:
  - New `_detect_infra_types()` function detects Terraform, Kubernetes, AWS, GCP, and Azure from project markers and home config directories.
  - Added utility tools to detection: `jq`, `curl`, `gh`, `make`, `rg`, `rtk`.
  - Added CLI hints for tool preferences (e.g., `rg` over `grep`, `jq` for JSON extraction).
  - Token limit now shown in system context.
  - Deduplication of tool labels to avoid repeated entries.

- **Improvement: Prompt Refinements**:
  - `persona.md`: "Calibrate depth" → "Depth matches content"; added "Push back" rule.
  - `mandate.md`: Major restructure — added Pre-Task Clarity, Execution Loop, Scope & Simplicity sections; expanded edge case guidance; reorganized rule priorities.
  - Updated tool guidance in `chat.py` for `ActivateSkill`, `DelegateToAgent`, `DelegateToAgentsParallel`, and `Bash`.

## 2.22.0 (April 16, 2026)

- **Feature: Global Model Getter/Renderer on LLMConfig**:
  - New `model_getter` and `model_renderer` properties on `LLMConfig` for global model transformation hooks.
  - New `resolve_model(base_model=None)` method applies getter then renderer in sequence.
  - Enables centralized model tiering, A/B routing, and provider mapping across all agents.
  - Task-level `model_getter`/`model_renderer` take precedence over config-level defaults.

- **Feature: Summarizer Agents Support Model Pipeline**:
  - `create_summarizer_agent()`, `create_conversational_summarizer_agent()`, `create_message_summarizer_agent()` now accept optional `model_getter` and `model_renderer` parameters.
  - Falls back to `llm_config.model_getter/model_renderer` when task-level hooks not provided.
  - Ensures background summarizer agents use consistent model transformation logic.

- **Feature: History Processor Model Pipeline**:
  - `create_summarizer_history_processor()` now accepts `model_getter` and `model_renderer` parameters.
  - Pre-creates conversational/message summarizer agents with getter/renderer when provided.
  - History compression agents now respect global model pipeline configuration.

- **Improvement: Sub-Agent Manager Model Resolution**:
  - `SubAgentManager` now uses `llm_config.resolve_model()` for sub-agent model resolution.
  - Passes config-level getter/renderer to history processor for consistent behavior.
  - All delegated sub-agents now go through the global model pipeline.

- **Improvement: Tool Sub-Agents Use resolve_model()**:
  - `analyze_file()` in `file.py` now uses `llm_config.resolve_model()`.
  - `_extract_info()` and `_summarize_info()` in `code.py` now use `llm_config.resolve_model()`.
  - `_summarize_web_content()` in `web.py` now uses `llm_config.resolve_model()`.
  - Ensures all background tool agents respect global getter/renderer hooks.

- **Improvement: Model-Tiering Example Enhanced**:
  - Example now registers renderer on `llm_config` for all sub-agents (web summarizer, code analyzer, history compressor).
  - Tier tracker is task-level only (main agent) — background agents don't consume the per-request tier budget.
  - Demonstrates separation of concerns: task-level tiering vs. global provider mapping.

- **Documentation: New Python API Section**:
  - Added "Python API: Model Getter & Renderer" section to `docs/configuration/llm-config.md`.
  - Documents hook signatures, `resolve_model()` behavior, and precedence rules.
  - Examples show global vs. task-level configuration patterns.
  - Lists all agent types affected by config-level hooks.

- **Tests: Coverage Expansion**:
  - Enhanced `test/llm/config/test_llm_config.py`: Model getter/renderer property tests (+81 lines).
  - Enhanced `test/llm/history_processor/test_history_summarizer.py`: Getter/renderer parameter tests (+35 lines).
  - Enhanced `test/llm/task/test_llm_chat_task.py`: Config-level fallback tests (+35 lines).
  - Enhanced `test/llm/task/test_llm_task.py`: Model pipeline resolution tests (+68 lines).

## 2.21.1 (April 16, 2026)

- **Bug Fix: Runner CLI UnboundLocalError**:
  - Fixed `UnboundLocalError: cannot access local variable 'session' where it is not associated with a value` in `src/zrb/runner/cli.py`.
  - Occurred when a task was interrupted (e.g., via `Ctrl+C`) before the `session` variable was assigned in the `try` block.
  - Added safe handling for `None` sessions in `_print_conversation_name`.

## 2.21.0 (April 16, 2026)

- **Feature: Tool Guidance System**:
  - New `ToolGuidance` dataclass in `src/zrb/llm/prompt/tool_guidance.py` for declarative per-tool usage hints.
  - `add_tool_guidance()` method on `LLMChatTask` and `LLMTask` registers static guidance entries.
  - `add_tool_guidance_factory()` method on `LLMChatTask` registers dynamic guidance (e.g., config-dependent tool names).
  - `PromptManager` composes a `# Tool Usage Guide` section from registered guidance, automatically inserted between mandate and journal sections.
  - Guidance for unregistered tools is suppressed at runtime — `LLMChatTask._exec_action` sets `prompt_manager.tool_names` from the resolved tool list.
  - New `CFG.LLM_INCLUDE_TOOL_GUIDANCE` config toggle (default: `on`). Set `ZRB_LLM_INCLUDE_TOOL_GUIDANCE=0` to disable.
  - All built-in tools ship with pre-registered guidance covering when-to-use and key behavioral rules (File Operations, Execution, Analysis, Research & Web, Planning, Git Worktrees, LSP, Zrb Tasks, Delegation).
  - Guidance for factory-created tools (`ListZrbTasks`, `RunZrbTask`, `ActivateSkill`, `DelegateToAgent`, `DelegateToAgentsParallel`) uses `add_tool_guidance_factory()` to resolve dynamic names.
  - `ToolGuidance` exported from `zrb.__init__` for public API access.

- **Feature: Tool Wrapper for Structured Error Handling**:
  - New `tool_wrapper` decorator in `src/zrb/llm/tool/_wrapper.py` catches tool exceptions and returns structured `{"error": "..."}` messages instead of raising.
  - Applied to worktree tools (`enter_worktree`, `exit_worktree`, `list_worktrees`), delegate tools, and file tools (`list_files`, `glob_files`).
  - LLM agent continues operating after tool errors instead of crashing the session.

- **Refactoring: Tool Return Value Standardization**:
  - `glob_files` now returns `{"files": [...], "truncation_notice": "..."}` instead of a flat list.
  - `list_files` returns `{"error": "..."}` for nonexistent paths instead of raising `FileNotFoundError`.
  - Consistent structured output format across file, search, and worktree tools.

- **Improvement: Prompt Optimization**:
  - Slimmed down prompt markdown files: `persona.md`, `mandate.md`, `git_mandate.md`, `journal_mandate.md`, `conversational_summarizer.md`, `message_summarizer.md`.
  - Extracted tool-specific guidance from docstrings into explicit `add_tool_guidance()` registrations in `chat.py`.
  - Reduced token usage in system prompts by moving verbose MANDATES from docstrings to the tool guidance section.

- **Improvement: System Context Refactoring**:
  - Restructured `system_context.py` for cleaner prompt composition and maintainability.

- **Improvement: Web Tool Enhancements**:
  - Enhanced `web.py` with improved URL handling and content fetching.
  - Better error messages and structured returns for web operations.

- **Improvement: Delegate Tool Error Messages**:
  - `DelegateToAgent` returns structured `"Error: ..."` messages instead of raising `ValueError`.
  - `DelegateToAgentsParallel` reports `"Error: ..."` instead of `"failed"` for consistency with other tools.

- **Documentation: New and Expanded Docs**:
  - New "LLM Prompt System" section in `AGENTS.md` documenting `PromptManager` composition and `add_tool_guidance()` API.
  - Expanded `docs/advanced-topics/llm-integration.md`: Added detailed tool reference tables (File, Analysis/LSP, Planning, Git Worktrees, Zrb Tasks) and new "Tool Guidance" section with static and dynamic registration examples.
  - Expanded `docs/configuration/llm-config.md`: Added `ZRB_LLM_INCLUDE_TOOL_GUIDANCE` variable and tool guidance configuration guide.

- **Tests: Coverage Expansion**:
  - New `test/llm/prompt/test_tool_guidance.py`: Tool guidance prompt rendering (+100 lines).
  - Enhanced `test/llm/prompt/test_manager.py`: Tool guidance manager integration (+99 lines).
  - Enhanced `test/llm/prompt/test_claude.py`: Claude prompt tests (+41 lines).
  - Updated `test/llm/prompt/test_system_context.py`: Refactored for new structure.
  - Enhanced `test/llm/tool/test_file.py`: Structured return values for `glob_files`, `list_files`, `search_files`; new tests for `replace_in_file` near-match suggestions, multiple matches with `count`, `search_files` files_only/case_insensitive/context_lines (+130 lines).
  - Updated `test/llm/tool/test_delegate_tool.py`: Error handling returns structured messages instead of raising.
  - Updated `test/llm/tool/test_worktree.py`: Error handling returns structured messages instead of raising.
  - Updated `test/llm/tool/test_plan.py`: Compact todo format assertions.

## 2.20.2 (April 15, 2026)

- **Security: Dependency Vulnerability Patches**:
  - Updated `Pillow` from `>=10.0.0` to `>=12.2.0` (CVE-2026-40192: decompression bomb via unlimited GZIP read in FITS decoding).
  - Updated `pytest` from `^8.3.5` to `>=9.0.3` (CVE-2025-71176: local privilege escalation via `/tmp/pytest-of-{user}` directories).

- **Bug Fix: SharedContext Mutable Default Arguments**:
  - `SharedContext.__init__` changed mutable defaults (`={}`, `=[]`) to `None` with proper initialization, preventing shared state between instances.

- **Bug Fix: Session.get_root_tasks() Infinite Recursion**:
  - Replaced recursive `get_root_tasks()` with iterative traversal using a visited set to prevent infinite loops with cyclic task graphs.

- **Bug Fix: Session.terminate() Mutation During Iteration**:
  - Wrapped `dict.values()` and `list` iterations with `list()` to prevent "dictionary changed size during iteration" errors during session termination.

- **Bug Fix: State Logger CPU Consumption**:
  - Changed state logger sleep from `asyncio.sleep(0)` to `asyncio.sleep(0.1)`, capping writes at ~10 per second instead of spinning at full CPU.

- **Bug Fix: Builtin Plugin Path Resolution**:
  - Fixed `Path(os.path.dirname(__file__)).parent` to `Path(__file__).parent.parent.parent` for correct builtin path in `SkillManager`, `HookManager`, and `SubAgentManager`.

- **Refactoring: Modernize Type Annotations**:
  - Replaced `Optional[X]` → `X | None`, `Union[X, Y]` → `X | Y`, `Dict` → `dict`, `List` → `list`, `Tuple` → `tuple` across LSP, agent, prompt, and tool modules.

- **Refactoring: Path Handling Migration**:
  - Replaced `os.path.dirname(__file__)` + `os.path.join` with `Path(__file__).parent` / path operations across all web route modules and prompt loading.

- **Refactoring: Deduplicate Agent Search Directory Logic**:
  - Extracted `_add_agents_from_root()` method in `SubAgentManager` to eliminate repeated directory scanning code across user home, project, and base search sections.

- **Refactoring: Deduplicate Task Group Execution**:
  - Extracted `_execute_task_group()` and `_skip_task_group()` helper functions in `execution.py` to reduce duplication in successor/fallback execute and skip logic.

- **Refactoring: Deduplicate BaseTask Append Methods**:
  - Extracted `_append_unique_tasks()` method in `BaseTask` to consolidate `append_fallback`, `append_successor`, `append_readiness_check`, and `append_upstream`.

- **Refactoring: Deduplicate File List Truncation**:
  - Extracted `_truncate_file_list()` helper in `file.py` to share truncation logic between `list_files()` and `glob_files()`.

- **Documentation: New and Expanded Docs**:
  - New `docs/advanced-topics/mcp-support.md`: MCP server configuration and discovery guide.
  - Expanded `docs/advanced-topics/llm-integration.md`: Added "Built-in LLM Tools" reference section covering all built-in tool categories.
  - Expanded `docs/advanced-topics/maintainer-guide.md`: Added "Context Propagation Internals" section documenting `ContextVar` usage patterns.
  - Expanded `docs/advanced-topics/upgrading-guide.md`: Added "Upgrading from 1.x.x to 2.x.x" section with migration table.
  - Expanded `docs/core-concepts/session-and-context.md`: Added "Ambient Context" section documenting `get_current_ctx()` and `zrb_print()`.

- **Tests: Coverage Expansion**:
  - New `test/llm/lsp/test_lsp_protocol.py`: LSP protocol data structures (+345 lines).
  - New `test/llm/prompt/test_system_context.py`: System context prompt generation (+228 lines).
  - New `test/llm/tool_call/test_read_file_validation.py`: Read file validation (+48 lines).
  - New `test/llm/tool_call/test_replace_in_file_validation.py`: Replace-in-file validation (+96 lines).
  - New `test/llm/tool_call/tool_policy/test_auto_approve.py`: Auto-approve policy (+221 lines).
  - New `test/task/base/test_monitoring.py`: Task monitoring (+437 lines).
  - New `test/session/test_session.py`: Session lifecycle and root task detection (+145 lines).
  - Enhanced `test/task/base/test_execution.py`: Execution helpers and task group logic (+222 lines).
  - Enhanced `test/task/test_lifecycle.py`: State logger timing and lifecycle (+177 lines).
  - New `test/builtin/llm/test_chat_tool_policy.py`: Chat tool policy (+131 lines).
  - New `test/runner/web_route/test_task_input_api.py`, `test_logout_api_route.py`, `test/runner/web_schema/test_web_user_schema.py`, `test/llm/agent/test_common.py`, `test/util/test_util_group.py`, `test/input/test_base_input.py`.

- **Maintenance: Dependency Updates**:
  - Updated `poetry.lock` with latest compatible versions.

## 2.20.1 (April 13, 2026)

- **Improvement: Parallel Chunk Summarization**:
  - `chunk_and_summarize()` now runs all chunks concurrently via `asyncio.gather` instead of sequentially.
  - Up-front chunk building provides total count before launching tasks.
  - Progress indicator shows `Compressing chunk X/total (N messages)...`
  - Errors from individual chunks still propagate correctly.

- **Improvement: Tool Call Preparation Indicator**:
  - New static `🔄 Prepare tool parameters...` indicator on `PartStartEvent(ToolCallPart)`.
  - Providers that stream deltas (OpenAI, Anthropic) overwrite the static line with the animated spinner.
  - Providers that don't stream (e.g., Ollama) leave the static line visible for better feedback.
  - New `was_tool_call_start` flag ensures clean transitions between static and animated states.

- **Improvement: Worktree Repo-Local Storage**:
  - Worktrees now placed inside the repo under `.{ROOT_GROUP_NAME}/worktree/` instead of system temp directory.
  - Uses `git rev-parse --show-toplevel` to resolve the git repo root.
  - Keeps worktrees co-located with the repository they belong to.

- **Feature: Bidirectional Journal Graph**:
  - Journal restructured as a bidirectional graph with a backlinks protocol.
  - Every forward link must have a backlink entry in the target note's `## Backlinks` section.
  - New Link Convention with relative paths from the journal root.
  - Step-by-step guide for creating new notes with proper backlink maintenance.
  - Updated `journal_mandate.md` with embedded index context and retrieval guidance.
  - Updated `core-journaling` skill with backlink protocol, maintenance rules, and ~50-line file limit guidance.

- **Improvement: Active Skills Tracking in Summarizer**:
  - New `<active_skills>` section in the `conversational_summarizer.md` state snapshot XML.
  - Skills activated via `ActivateSkill` are now tracked and restored on context recovery.
  - Restored agent re-activates skills if the task still requires that domain expertise.

- **Improvement: Mandate Updates**:
  - Added "Memory Operations" as rule priority #4: journaling and skill activation are autonomous; exempt from Scope Discipline.
  - Marked Delegation and Skills sections with `*(if available)*` conditional markers.
  - Added `WriteMany`, `ClearTodos`, `ExitWorktree`, `ListWorktrees` to tool selection table.
  - Marked conditional tools with `*(if available)*` in the tool selection table.

- **Improvement: Tool Docstring Updates**:
  - `WriteTodos`: Replaced "Create todos before starting complex multi-step tasks" mandate with "Call `GetTodos` before each subtask to check current state".
  - `OpenWebPage`: Reformatted `MANDATE` to `MANDATES` with bulleted guidance.

- **Maintenance: Dependency Updates**:
  - Updated `pydantic-ai-slim` from `~1.76.0` to `~1.80.0`.
  - Updated `pydantic-graph` from `1.76.0` to `1.80.0` (transitive).
  - Updated `poetry.lock` with latest compatible versions.

## 2.20.0 (April 12, 2026)

- **Feature: Rewind/Snapshot System**:
  - New `SnapshotManager` class using shadow git repositories for filesystem snapshots.
  - `/rewind` command restores filesystem and conversation history to a previous state.
  - Snapshots track message count for consistent history restoration.
  - Config: `LLM_ENABLE_REWIND=on`, `LLM_SNAPSHOT_DIR`, `LLM_UI_COMMAND_REWIND`.
  - Default snapshot location: `~/.zrb/llm-snapshots/`.
  - New `enable_rewind` and `snapshot_dir` parameters on `LLMChatTask`.

- **Feature: PowerShell Autocomplete**:
  - New `zrb shell autocomplete powershell` command generates PowerShell completion script.
  - Native `Register-ArgumentCompleter` integration for dynamic CLI completion.
  - Mirrors bash completion behavior with proper partial word handling.

- **Feature: Configurable Magic Numbers**:
  - All timeout, interval, size, and retry values now configurable via environment variables.
  - Timeout configs (milliseconds): `LLM_SSE_KEEPALIVE_TIMEOUT`, `LLM_REQUEST_TIMEOUT`, `LLM_WEB_PAGE_TIMEOUT`, etc.
  - Interval configs (milliseconds): `LLM_UI_STATUS_INTERVAL`, `LLM_UI_REFRESH_INTERVAL`, `SCHEDULER_TICK_INTERVAL`, etc.
  - Size/Limit configs: `LLM_MAX_COMPLETION_FILES`, `LLM_FILE_READ_LINES`, `LLM_MAX_OUTPUT_CHARS`, etc.
  - Retry configs: `LLM_MAX_CONTEXT_RETRIES`, `LLM_TOOL_MAX_RETRIES`, `LLM_MCP_MAX_RETRIES`.
  - Pagination configs: `WEB_SESSION_PAGE_SIZE`, `WEB_API_PAGE_SIZE`.

- **Feature: Model Visibility Controls**:
  - `LLM_SHOW_OLLAMA_MODELS`: Enable/disable Ollama models in `/model` autocomplete.
  - `LLM_SHOW_PYDANTIC_AI_MODELS`: Enable/disable pydantic-ai built-in models in autocomplete.
  - Useful for environments without Ollama or when using custom model registries.

- **Breaking Change: Hooks Timeout Unit**:
  - `HOOKS_TIMEOUT` changed from seconds (30) to milliseconds (30000).
  - Existing configs with `ZRB_HOOKS_TIMEOUT=30` will now timeout after 30ms.
  - Update your config to `ZRB_HOOKS_TIMEOUT=30000` for equivalent behavior.

- **Improvement: Documentation**:
  - Expanded `docs/configuration/llm-config.md` with all configurable timeout/interval/size values.
  - Added detailed descriptions for new environment variables.

- **Tests: Coverage Expansion**:
  - New `test/llm/snapshot/test_manager.py`: Snapshot manager tests (+367 lines).
  - New `test/llm/tool/test_file.py`: File tool tests (+313 lines).
  - New `test/llm/prompt/test_claude.py`: Claude prompt tests (+398 lines).
  - New `test/config/test_config.py`: Config property tests (+278 lines).
  - New `test/llm/util/test_history_formatter.py`: History formatter tests (+145 lines).
  - Enhanced SSE stream, completion, and command tests.

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

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)