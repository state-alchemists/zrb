🔖 [Documentation Home](../README.md)

## 2.22.8 (April 26, 2026)

- **Feature: Tool Guidance Propagation to Sub-Agents**:
  - Tool guidance now registered on both `llm_chat` (main agent) and `sub_agent_manager` (sub-agents) in `src/zrb/builtin/llm/chat.py`.
  - Refactored static tool guidance from individual `llm_chat.add_tool_guidance(...)` calls to a shared `_static_tool_guidance` list broadcast to both agents.
  - Sub-agents now receive the same tool usage guidance as the main agent, improving delegation consistency.

- **Feature: `add_tool_guidance()` on `SubAgentManager`**:
  - New `add_tool_guidance()` and `add_tool_group()` methods on `SubAgentManager` (`src/zrb/llm/agent/subagent/manager.py`).
  - `create_agent()` now appends tool guidance prompt to sub-agent system prompts via `get_tool_guidance_prompt()`.
  - Ensures delegated sub-agents have tool usage instructions in their system context.

- **Improvement: Mandate Refinements**:
  - Renamed "Pre-Task Clarity" to "Inquiries vs. Directives & Pre-Task Clarity" with explicit distinction between inquiry vs. directive user intent.
  - New "Technical Integrity & Standards" section: no hacks, idiomatic code, verify dependencies.
  - New "Context & Token Efficiency" section: parallelism guidance for independent tool calls.
  - Renamed "Execution Loop" to "Execution Loop (Path to Finality)" with structured phases: Empirical Reproduction, Mandatory Verification, Strategic Re-evaluation (3-strike rule).
  - Removed redundant "Ask the user only when genuine ambiguity remains after step 1."

- **Improvement: Persona Refinements**:
  - Identity now describes the LLM as "Lead Engineer and Strategic Orchestrator" with context window as precious resource.
  - "No preamble" replaced with more specific "One sentence before tools" calibration.
  - Added periods at end of all bullet points for consistency.

- **Improvement: DelegateToAgent Guidance Refined**:
  - Updated `DelegateToAgent` guidance to emphasize delegating heavy/repetitive work while keeping the main session history lean.

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

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)