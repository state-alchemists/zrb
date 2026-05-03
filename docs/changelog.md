🔖 [Documentation Home](../README.md)

## 2.24.3 (May 3, 2026)

- **Improvement: LLM Prompt & Skill Verbosity Audit**:
  - Comprehensive word-level audit across all prompt components, skills, and agent definitions. Every retained word was justified; any word whose removal would not degrade agent behavior was cut (~25–30% reduction overall).
  - `mandate.md`: Rewritten for conciseness — tightened all sections, made idiom rules language-agnostic (replaced JS-specific "composition over complex inheritance" with "never mutate or annotate objects you don't own"), quantified "when unclear" priority as `correctness > speed, brevity > completeness, action > analysis`, collapsed redundant scope rules.
  - `persona.md`: Removed "Strategic Orchestrator" framing; simplified to "Lead Engineer" identity with "context window is precious; delegate complex or repetitive work."
  - `journal_reminder.md`: Rewrote to prevent re-scanning already-journaled items — now instructs scanning from the turn after the last journal write, not the full session history.
  - `journal_mandate.md`: Condensed write criteria to one directive line.
  - `git_mandate.md`: Added "If the diff exceeds ~100 lines, show a per-file summary instead" rule.
  - `conversational_summarizer.md`: Added `[BLOCKED: reason]` status for goals that become impossible; clarified "fully analyzed" definition (role, key functions/classes, and dependencies understood).
  - `web_summarizer.md`: Marketing claims now rated `LOW (Omit unless directly answering the query)`.
  - `file_extractor.md`: Extended file type coverage: `.sh`/`.bash`/`.ps1` (Scripts), `.sql` (Database), `.ts`/`.rs`/`.java` (Source), `.ini`/`.env` (Configuration), `.rst` (Documentation).

- **Improvement: Skill Rewrites**:
  - `core-coding/SKILL.md`: Added Supplementary Skill Gates table at top (testing / debug / refactor / review trigger conditions); added Language & Framework Idioms rule to Strategy phase; added reference-check mandate for signature changes (`LspFindReferences`) and file moves/removes (`Grep`).
  - `debug/SKILL.md`: Removed persona intro; added multi-language root causes (Rust/C++ ownership, JS coercion alongside Python); specified instrumentation placement ("at failure points: entry/exit, before/after suspect operations").
  - `testing/SKILL.md`: Removed Testing Specialist persona; tightened mode descriptions; mock threshold now `~1 second per test`.
  - `refactor/SKILL.md`: Removed Refactoring Mode intro; renamed table column "When to Apply" → "Trigger" with tighter descriptions; removed verbose code smell examples.
  - `review/SKILL.md`: Removed Auditor Mode intro; removed path traversal example; large diff threshold defined as `>10 changed files or >500 total changed lines`.
  - `research-and-plan/SKILL.md`: Removed Architect/Analyst Mode intro; condensed clarification rules and delegate shorthand.
  - `core-journaling/SKILL.md`: Trimmed "Core Philosophy" header and opening.
  - `init/SKILL.md`: Specified representative file selection: "main entry point, one domain model or core service, and one test file."

- **Improvement: Agent Definition Updates**:
  - `generalist.agent.md`: Removed persona fluff (Polymath Executor / Swiss Army Knife); removed duplicated "Available Tools" section (frontmatter is canonical); added `RM`, `MV`, `SearchJournal`, worktree tools (`EnterWorktree`, `ExitWorktree`, `ListWorktrees`), and all LSP tools.
  - `code-reviewer.agent.md`: Removed "Code Auditor" persona section; added `SearchJournal`; added language/framework idiom check to Maintainability dimension; condensed test-run section.
  - `researcher.agent.md`: Added `SearchJournal` + full LSP tool suite (`LspFindDefinition`, `LspFindReferences`, `LspGetDiagnostics`, `LspGetDocumentSymbols`, `LspGetWorkspaceSymbols`, `LspGetHoverInfo`, `LspListServers`) to tool list.

- **Improvement: `AGENTS.md` Accuracy**:
  - Removed stale `llm/chat/` row (directory is empty; `LLMChatTask` lives in `llm/task/chat/`).
  - Fixed ambient state paths: `run_agent.py` → `agent/run/runner.py`; `runtime_state.py` → `agent/run/runtime_state.py`.
  - Updated `llm_plugin/` description to name `skills/` and `agents/` subdirectories explicitly.

- **Improvement: RM Tool Guidance**:
  - `chat.py`: RM reference-check now reads "use Grep (or LspFindReferences)" to match MV guidance consistency.

- **Maintenance: Remove Stale FastApp Images**:
  - Deleted unused `_images/fastapp/` image assets no longer referenced.

## 2.24.2 (May 3, 2026)

- **Bug Fix: Summarizer Token Threshold Now Accounts for System Prompt**:
  - The history summarizer was comparing message-history token count against `conversational_token_threshold` without deducting the system prompt's token cost, causing summarization to trigger later than intended (the usage indicator's "Total" includes the system prompt).
  - `_prepare_history` in `runner.py` now counts system prompt tokens before invoking history processors and passes the count as a `system_prompt_overhead` argument directly to each processor.
  - `create_summarizer_history_processor` inner function `process_history` accepts `system_prompt_overhead: int = 0` and computes `adjusted_threshold = conversational_token_threshold - system_prompt_overhead` for all threshold comparisons.
  - Replaces the previous hacky side-channel that set `processor._system_prompt_overhead` as an attribute on the callable.

## 2.24.1 (May 3, 2026)

- **Bug Fix: Consecutive Failure When Reducing History**:
  - `drop_oldest_turn()` in `history_utils.py` now accepts a `min_turns` parameter and refuses to drop a turn when doing so would leave fewer turns than the minimum.
  - `_execution_loop` passes `min_turns=1` to `handle_stream_error` when deferred tool results are pending, preventing the history from being pruned down to zero turns mid-tool-call — which caused consecutive context-too-long failures with no recovery path.

- **Performance: `fit_context_window` O(n²) → O(n)**:
  - The pruning loop in `LLMLimiter.fit_context_window` previously called `_count_tokens(pruned_history)` on every iteration, re-stringifying the entire remaining history each time — O(n²) across all pruning steps.
  - Now precomputes per-message body token counts and a backward-scanned `last_instr_from[]` index in one O(n) pass. The pruning loop subtracts costs incrementally and updates the active instruction cost in O(1) per step, giving O(n) total.
  - Correctly replicates `_to_str`'s list-level semantics: message bodies are counted with `skip_instructions=True` and only the last instruction in the remaining window is counted once.
  - Measured speedup: ~5× at 40 turns, ~11× at 80 turns, ~22× at 160 turns, ~46× at 320 turns.

- **Performance: Deduplicated Token Count in `_prepare_history`**:
  - `_prepare_history` previously called `limiter.count_tokens(message_history)` twice per turn — once for the `PRE_COMPACT` hook payload and once for the context-limit check — even though both operate on the same content when no history processors are registered.
  - The count is now computed once and reused when `history_processors` is empty (the common case), saving one O(n) traversal per chat turn.

## 2.24.0 (May 1, 2026)

- **Feature: New `remove_file` and `move_file` Agent Tools**:
  - Added `remove_file` tool (`RM`) for deleting files and directories, with a `recursive` flag for directory removal.
  - Added `move_file` tool (`MV`) for moving or renaming files, with automatic parent directory creation.
  - Both tools include comprehensive tool guidance: `RM` warns about dangling references and irreversible directory removal; `MV` guides import/reference updates.
  - New `approve_if_mv_inside_journal_dir()` auto-approval policy for `MV` operations within the journal directory.
  - Registered in `llm_chat` toolset and linked via `chat_tool_policy.py`.

- **Feature: New `search_journal` Agent Tool**:
  - Added `SearchJournal` tool for searching past journal entries by keyword or regex pattern.
  - Targets the configured journal directory only; case-insensitive by default.
  - Auto-approved tool (no user confirmation needed).

- **Feature: System Context Tool Auto-Detection**:
  - `system_context.py` now auto-detects available CLI tools (`docker`, `python`, `node`, `go`, `jq`, `curl`, `gh`, `make`, `rg`, `rtk`) by checking `$PATH`.
  - Detects project type from markers (`pyproject.toml`, `go.mod`, `Cargo.toml`, `package.json`, etc.) and advertises relevant build tools.
  - Detects infrastructure tools (Terraform, Kubernetes, AWS, GCP, Azure) from project markers and home config directories.
  - Displays token limit in system context for budget awareness.
  - Uses `ThreadPoolExecutor` for parallel `shutil.which()` checks to minimize startup latency.

- **Refactoring: `run_agent` God Function Split**:
  - The monolithic 952-line `run_agent()` body (~640-line diff) was extracted into focused helper functions:
    - `_resolve_context_dependencies()` — resolves UI, tool confirmation, YOLO, approval channel, and hook manager with fallback logic.
    - `_setup_print_and_events()` — resolves print function and streaming event handler.
    - `_run_startup_hooks()` — executes session-start and user-prompt-submit hooks with `additionalContext` processing.
    - `_log_startup()` — debug logging of resolution results, extracted for testability.
  - Main `run_agent()` now reads as a clean orchestration pipeline: resolve → set context vars → setup → hooks → prepare history → execution loop with `try/finally` cleanup.
  - Removed stale imports (`DeferredToolRequests`, `DeferredToolResults`, `UserPromptPart`, `extract_replace_response`, `extract_system_message`).

- **Bug Fix: YOLO Inheritance Checker Wrong Arguments**:
  - `make_yolo_inheritance_checker()` was receiving incorrect arguments (`ctx`, `tool_def`, `args`) from pydantic-ai's approval callback, causing `TypeError` on most calls.
  - Simplified to `check_yolo_inheritance(tool_def)` — only the tool definition is needed for the check.
  - Callers in `common.py` updated from `try/except TypeError` fallback to a clean single call.
  - Fixes a regression where `yolo` mode would not properly auto-approve agent tool calls.

- **Bug Fix: History Summarization Silently Discarded**:
  - pydantic-ai's `Agent` constructor applies `history_processors` on a shallow copy of `message_history` without writing back, making summarization a no-op.
  - Removed `history_processors=history_processors` from `Agent()` constructor call.
  - Stored processors as `agent._zrb_history_processors` and now apply them in `_prepare_history` (before first model call) and `_execution_loop` (between tool-call iterations) where the caller owns the history reference.

- **Bug Fix: Subagent Agent Search Path**:
  - Fixed `builtin_path` resolution in `SearchMixin`: parent traversal was off by one level, causing sub-agent discovery to miss the built-in agents directory.

- **Improvement: Prompt and Mandate Refinements**:
  - `mandate.md`: Added "Edge Cases" section for lock files, merge conflicts, test failures, and git hooks.
  - `persona.md`: Restructured with clearer "Response Calibration" subsection.
  - Updated tool guidance in `chat.py` for RM, MV, SearchJournal tools; Bash tool guidance now mentions `rtk gain` and `rtk` prefix for token savings.
  - Skills section now uses `skill_manager.get_skills()` instead of `scan()` to respect already-cached/injected skills.
  - `journal_mandate.md`: Minor clarity improvements.

- **Improvement: Tool Guidance Refinements**:
  - `Bash` timeout guidance updated from 30s to 120s (default).
  - Guidance now references `rtk` for token-efficient command execution.
  - `Write` guidance: calls out "For existing files, read with Read first to confirm content before overwriting."
  - `Edit` guidance: calls out "Before editing a function, method, or class: use Grep (LspFindReferences if LSP is available) to find all call sites."
  - `Delegation` guidance: references all available agent names (`code-reviewer`, `researcher`, `generalist`).

- **Maintenance: Dependency Update**:
  - Updated `pydantic-ai-slim` version in `poetry.lock` and `pyproject.toml`.

- **Tests: Coverage Expansion**:
  - New `test/llm/agent/run/test_history_utils.py`: 115 lines covering history utility functions.
  - New `test/llm/tool/test_file_mv.py`: 61 lines for move_file tool.
  - New `test/llm/tool/test_file_rm.py`: 63 lines for remove_file tool.
  - New `test/llm/tool/test_journal.py`: 105 lines for SearchJournal tool.
  - New `test/llm/lsp/test_configs.py`: 93 lines for LSP server configuration.
  - New `test/llm/ui/test_buffered_output_mixin.py`: 95 lines for buffered output testing.
  - New `test/llm/ui/test_event_driven_ui.py`: 79 lines for event-driven UI testing.
  - New `test/llm/ui/default/test_keybindings_mixin.py`: 306 lines for keybindings lifecycle and rendering.
  - Extended `test/llm/ui/default/test_lifecycle_mixin.py`: +103 lines.
  - Updated `test/llm/hook/test_hook_result_processing.py`, `test/llm/ui/base/test_commands_mixin.py`, and `test/llm/ui/default/test_output_mixin.py`.

## 2.23.1 (April 28, 2026)

- **Bug Fix: Bedrock Nil-Content Compatibility**:
  - `_filter_nil_content()` in `src/zrb/llm/agent/run/history_utils.py` now uses `"."` instead of `""` for nil/empty content replacement.
  - Bedrock rejects blank text fields (`ValidationException`) and Anthropic models on Bedrock reject whitespace-only text.
  - Matches pydantic-ai's own Bedrock model convention of using `"."` as a minimal non-empty placeholder.

## 2.23.0 (April 27, 2026)

- **Breaking Change: Consolidated Model Resolution Pipeline**:
  - Removed `model_getter` and `model_renderer` properties from `LLMTask` (`src/zrb/llm/task/llm_task.py`) and `LLMChatTask` (`src/zrb/llm/task/chat/`).
  - `LLMConfig.resolve_model()` is now the single entry point for all model resolution.
  - Simplified `LLMChatTask` builder mixin by removing `model_getter`/`model_renderer` overrides; all model pipeline hooks now go through `LLMConfig`.
  - `create_agent()`, `SubAgentManager`, summarizer agents, history processors, hook creators, and UI commands all consistently use `LLMConfig.resolve_model()`.
  - Removes the task-level model-getter/renderer override pattern introduced in 2.22.0 in favor of a single config-level pipeline.

- **Improvement: `create_agent()` Default Retries Changed**:
  - `create_agent()` in `src/zrb/llm/agent/common.py` now uses `CFG.LLM_TOOL_MAX_RETRIES` as the default retry count instead of hardcoded `1`.
  - Ensures agent creation retries align with the configured tool retry policy across all callers.

- **Improvement: `filter_nil_content()` Preserves Message Structure**:
  - `_filter_nil_content()` in `src/zrb/llm/agent/run/history_utils.py` now replaces nil/empty content with an empty `TextPart("")` instead of dropping it from the message parts list.
  - Prevents structural issues with providers that expect at least one content part in each message.

- **Improvement: `/model` Command Uses `resolve_model()`**:
  - The `/model` slash command in `commands_mixin.py` now calls `LLMConfig.resolve_model()` instead of directly accessing `model_getter`/`model_renderer`.
  - Displays the fully resolved model name after pipeline transformation.

- **Maintenance: Example and Test Cleanup**:
  - Updated `examples/model-tiering/` README and `zrb_init.py` to use config-level resolution instead of task-level overrides.
  - Removed obsolete tests for removed `model_getter`/`model_renderer` properties.
  - Added new tests for `create_agent()` retries in `test/llm/agent/test_common.py`.
  - Cleaned up test coverage in `test/llm/task/` and `test/llm/history_processor/` to match the simplified API surface.

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