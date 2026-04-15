🔖 [Documentation Home](../README.md)

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