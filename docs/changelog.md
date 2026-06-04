🔖 [Documentation Home](../README.md)


## 2.32.0b3 (June 4, 2026)

- **Fix: History summarizer orphaning deferred-tool metadata (ADR-0058)**:
  - Deferred tool results (`_handle_deferred_tool_results`) could raise `UserError` when the summarizer compressed away the `ModelResponse` whose `tool_calls` matched `current_results` — causing an infinite retry death spiral. Two defences: (1) `retry_loop.py` catches the specific `UserError`, clears stale `current_results`, and retries with intact history; (2) `runner.py` skips the summarizer between deferred-tool iterations when pending results exist.
  - Changelog note for summarization fixes between b2 and b3 see full ADR-0058 in `docs/adr/06-llm-core.md`.

- **Fix: `_merge_consecutive_messages` in-place history mutation**:
  - `runner.py`: `_merge_consecutive_messages` appended `UserPromptPart` directly to `current_history[-1]`, which was aliased to `FileHistoryManager`'s cached list — grafting the turn's prompt onto stored history for duplication on the next save/cancel path. Now builds a new `ModelRequest` via `replace()`.

- **Fix: History file corruption recovery**:
  - `file_history_manager.py` `_clean_*` methods now preserve unknown fields via `**data` (was dropping `ThinkingPart.signature`, `RetryPromptPart.tool_name`/`tool_call_id`, etc.).

- **Fix: Model callback double-firing**:
  - `create_agent` in `agent/common.py` gained `resolve_model=False`. Callers that already resolved the model (LLMTask, SubAgentManager, summarizer, code tools, multimodal describer) now pass the flag to prevent `model_getter`/`model_renderer` from firing twice on an already-resolved value.

- **Fix: OpenAI content:null patch silently failing**:
  - `openai_patch.py` now verifies the target attribute exists before patching, and logs a `CFG.LOGGER.warning` (instead of `pass`) when pydantic-ai internals change — making DeepSeek/OpenAI-compatible provider regressions diagnosable.

- **Fix: `filter_nil_content` over-injecting `"(tool call)"` placeholder (ADR-0059)**:
  - Previously injected a `TextPart("(tool call)")` into *any* text-less `ModelResponse`, including tool-call-only turns. That placeholder leaked into history, and weaker models (observed: `deepseek-v4-flash` on ollama) learned to imitate `"(tool call)"` as literal output — one transcript had 29 placeholder turns then 3 imitation emissions. Now the placeholder is injected only when a `ModelResponse` has **neither** text **nor** tool calls. A tool-call-only turn is valid without text (every provider accepts it; `openai_patch` omits the `content` field), so no placeholder is needed.

- **Fix: Empty/placeholder completions no longer surfaced as final answer**:
  - `runner.py`: New `_is_empty_completion` guard catches blank strings and leaked `"(tool call)"` / `"(tool call"` output after the stream. On detection, `_history_without_trailing_response` drops the degenerate trailing `ModelResponse` and the turn is regenerated (bounded by `max_empty_completion_retries=2`). After exhaustion, raises a clear `RuntimeError` instead of showing the placeholder or looping forever. Structured outputs and `DeferredToolRequests` bypass the guard by construction.

- **Improvement: Tool error messages with actionable guidance**:
  - `file_read.py`, `file_edit.py`, `shell.py`: all error return paths now include a `[SYSTEM SUGGESTION]` prefix directing the model to the likely fix (check path, permissions, syntax, etc.).

- **Improvement: Summarizer safety and reliability**:
  - `chunk_processor.py`: `consolidate_summaries` accepts explicit `limiter` parameter.
  - `history_summarizer.py`: Uses `strip_orphaned_returns` (targeted removal) instead of wholesale `sanitize_history` after compression; passes `limiter` through to consolidation.
  - `message_processor.py`: Deduplicated safe-copy logic via `safe_copy_result` from `agent/common.py`.

- **Improvement: Cold-start optimization**:
  - Added `# lazy:` annotations to in-function imports across `commands_mixin.py`, `ui.py`, `deferred_calls.py`, `post_write_check.py`, `retry_loop.py`.

- **Improvement: tiktoken robustness**:
  - `limiter.py`: Broader `except Exception` (not just `ImportError`) in token counting and truncation — prevents tiktoken encoding/BPE failures from crashing the history pipeline before every model call.

- **Improvement: Content placeholders centralized**:
  - `message.py`: Introduced `TOOL_CALL_PLACEHOLDER`, `EMPTY_CONTENT_PLACEHOLDER`, `TOOL_RETURN_NULL_PLACEHOLDER` constants; all history-utils layers now reference these instead of scattered string literals.

- **Tests**: 3104 passed (no regression).

- **Documentation**:
  - ADR-0058 and ADR-0059 in `docs/adr/06-llm-core.md`.
  - Maintainer guide: new patterns (`resolve_model=False`, lazy import conventions) and "The Empty-Completion Guard" section.
  - AGENTS.md: `run_agent.py` → `agent/run/runner.py` reference fix.

## 2.32.0b2 (June 3, 2026)

- **Feature: `/model` subcommand for switching small and multimodal models**:
  - UI now supports `/model small <name>` and `/model multimodal <name>` in addition to `/model <name>`.
  - Tab-completion suggests subcommands and model names; setting the small/multimodal model updates `llm_config` instantly.
  - Summarizer agents are now created fresh per `process_history` call so `/model small` changes take effect immediately without a restart.

- **Improvement: Retry logic for summarization API errors**:
  - `text_summarizer.py`: All summarization calls (`summarize_short_text`, `summarize_long_text`, `summarize_text`) now retry transient API errors (5xx, 429) using `LLM_API_MAX_RETRIES` and `LLM_API_MAX_WAIT`, matching the retry behavior in the main agent loop.

- **Improvement: Targeted history sanitization after summarization**:
  - `message.py`: New `strip_orphaned_returns()` removes `ToolReturnPart`s whose matching `ToolCallPart` was dropped during summarization, while leaving pending calls intact.
  - `history_summarizer.py`: Replaced wholesale `sanitize_history()` after summarization with `strip_orphaned_returns()` — preserves the fix (removes orphaned returns) without re-running heavy sanitization passes unnecessarily.

- **Tests**: 3090 passed (no regression).

## 2.32.0b1 (June 3, 2026)

- **Feature: Todo progress visualization in the UI**:
  - `write_todos`, `update_todo`, and `clear_todos` now push a styled progress card to the active UI (TUI, StdUI, web) after every change, showing the updated todo list with per-item status icons and a progress bar.
  - Web frontend (`chat.js`/`chat.css`): new SSE handler and styles for `todo_progress` kind — renders a card with change banner, progress bar, stats, and full item list.
  - TUI/StdUI: `todo_progress` kind rendered at full opacity (no `stylize_faint`).
  - New ADR-0057 documenting the design: side-channel via `current_ui`, fire-and-forget, no tool contract changes.

## 2.32.0a2 (June 2, 2026)

- **Improvement: Prompt quality and journaling workflow**:
  - `persona.md`: Consolidated conciseness guidance into a single "be concise per phase" rule; removed redundant preamble/narration prescriptions.
  - `mandate.md`: Added "ask rather than guess" principle when defaults under uncertainty are insufficient. Refined regenerate-vs-patch criteria with concrete triggers (signature change, >50% replacement, structural flaw).
  - `journal_mandate.md`: Restructured to clearly separate activity (what was done) from insight (what was learned); added explicit "activate `core-journaling`" instruction before writing; removed `[[wikilinks]]`; reordered skip/order-of-operations for clarity.
  - New `core-journaling/templates/insight-note.md`: Standardized insight note format with frontmatter `slug`, backlinks protocol, and rules.
  - `core-journaling/SKILL.md`: Added insight-note template reference; fixed `Bash`→`Shell` tool reference; emphasized markdown links over `[[wikilinks]]`.

- **Fix: Config mixin type safety**:
  - `llm_content.py` and `llm_ui_styles.py`: Added `Protocol` host-class in `TYPE_CHECKING` block with explicit type annotations on all `self` parameters, enabling static analysis to verify attribute access between mixin and composed Config class.

- **Fix: Documentation accuracy** (27 files, 284 insertions, 157 deletions):
  - Maintainer guide: llm-challenges section now points to `github.com/state-alchemists/llm-challenges` with updated clone commands and output paths. Added one-on-one LLM session section (`zrb chat "What is your honest analysis..."`).
  - Permission policy docs: Removed aspirational `RM`/`MV` tools from EDIT capability; fixed `ZRB_LLM_PERMISSIONS` env var example casing (`READ`→`read`); replaced non-existent `permissions=my_policy` on `LLMChatTask` with correct hook factory pattern.
  - `llmchat-task.md` constructor signature: Removed `dynamic_yolo` and `hook_manager` params (do not exist on `LLMChatTask`); added `render_system_prompt` and `ui_factory`; fixed `summarize_command`→`ui_summarize_commands`, `retries` default `2→0`; corrected `add_tool_guidance_factory` availability (available on both `LLMChatTask` and `LLMTask`).
  - Config docs: Fixed `ZRB_LLM_MODEL` default (`openai-chat:gpt-4o`), `ZRB_LLM_MULTIMODAL_MODEL` behavior (returns `None`, not a fallback), `ZRB_LLM_ASSISTANT_NAME` default (`"Zrb"`).
  - Hook docs: Added `.claude/hooks/` directory variants and plugin dirs to search path table; replaced broken `examples/hooks/` reference with `llm-hooks` example.
  - Fixed broken link in tasks-and-lifecycle.md (`./custom-tasks.md`→`../task-types/custom-tasks.md`).
  - Removed non-existent ULID tasks from builtin-helpers.md.

- **Fix: Example code accuracy**:
  - `permission-policy/` and `plan-mode/`: Rewrote from `permissions=my_policy` (non-existent param) to hook factory pattern using `set_current_permission_policy()`. Fixed README `--init` flag usage.
  - `web-auth/`: Replaced broken `@Task(...)` decorator with `@make_task(...)`.
  - `cmd-task/`: Fixed `retry`→`retries`, `retry_interval`→`retry_period`, removed non-existent `done_callback`.
  - `async-task/`: Fixed `retry=3`→`retries=3`.
  - `chat-minimal-ui/`, `chat-sse/`, `chat-telegram/`: Fixed import paths `zrb.llm.ui.simple_ui`→`zrb.llm.ui`.
  - `llm-hooks/`: Fixed `from zrb import llm_chat`→`from zrb.builtin.llm.chat import llm_chat`.
  - `chat-minimal-ui/README.md`: Updated 5× stale `examples/telegram-cli/`→`examples/chat-telegram/` references.
  - `cmd-task/README.md`: Fixed options table `retry`/`retry_interval`.

- **Tests**: No new tests (documentation and example fixes only).

## 2.32.0a1 (June 2, 2026)

- **Feature: Permission policy system (`PermissionPolicy`)**:
  - New `zrb/llm/permission/` package: `capability.py` (tool capability tags: `READ`, `EDIT`, `EXECUTE`, `NETWORK`, `DELEGATE`, `META`), `policy.py` (ordered first-match-wins `Rule`s with `allow`/`ask`/`deny` actions + `arg_pattern` glob), `state.py` (`current_permission_policy` + `current_agent_mode` `ContextVar`s).
  - `yolo` is now expressed as a `PermissionPolicy` via `from_yolo()` — characterization-test parity preserved.
  - Tools tagged centrally in `common_tools.py` via `zrb_capability`; untagged tools resolve to `UNKNOWN`.

- **Feature: Plan mode (read-only discovery)**:
  - New `plan_mode.py` tool (`EnterPlanMode`/`ExitPlanMode`, tagged `META`).
  - Plan mode is a preset `PermissionPolicy` (READ/NETWORK/META allow, EDIT/EXECUTE/DELEGATE deny).
  - Enforced by the execution gate in `agent/common.py` — same gate as the permission system.
  - System context line advertises active mode.
  - Examples in `examples/plan-mode/`.

- **Feature: Background subagents (`DelegateToAgentBackground`)**:
  - New `delegate_background.py` tool spawns a detached `asyncio` task; `GetDelegationResult(handle)` polls for completion.
  - Background tasks inherit the parent's permission policy and route approval requests to the parent UI's confirmation queue — no deadlocks, no silent auto-approve.
  - `BufferedUI` forwards approval requests under a lock; the default UI's `ask_user` is a confirmation queue.
  - Fan-out: start multiple background agents in parallel.

- **Feature: Shell tool replaces Bash as primary execution tool**:
  - New `shell.py`: `run_shell_command()` with streaming stdout/stderr, configurable truncation, timeout.
  - `Bash` (in `bash.py`) is now a thin backward-compat alias for `Shell`.
  - New `shell_background.py`: non-blocking shell execution with polling handle.
  - Background shell routes approvals through the same queue as background delegates.

- **Feature: Approval precedence chain**:
  - Clear delegation: `permission_policy → tool_policy → yolo`.
  - `deny` stops at the execution gate (no wasted prompts); `allow` bypasses all lower checks.
  - `LLMChatTask` and bare `LLMTask` converge on the same chain.
  - Background subagents auto-approve at the yolo level (never block the main agent), but `deny` rules still block.
  - Background yolo override in `subagent/yolo.py`.

- **Feature: Tool-output truncation backstop**:
  - Global cap (`LLM_MAX_TOOL_RESULT_CHARS`, default 100k) applied in tool wrappers.
  - Truncates model-facing `content` (head+tail with re-fetch hint); preserves structured `return_value`.
  - Config in `llm_limits.py`, implementation in `truncate.py`.

- **Improvement: Config system simplified with `EnvField` descriptor**:
  - New `config/env_field.py`: `EnvField` data descriptor replaces 700+ lines of repetitive `@property` getter/setter/`get_env`/`cast` boilerplate across all config mixins.
  - Config mixins (`llm_core`, `llm_limits`, `llm_prompt`, `llm_search`, `llm_ui_commands`, `llm_ui_runtime`, `llm_ui_styles`, `rag`, `task_runtime`, `web`, `hooks`, `internet_search`) migrated.
  - `contextvars.py` established as the canonical index of every `ContextVar` — three ownership homes, re-exported wrappers.

- **Improvement: UI enhancements**:
  - Confirmation queue in `default/confirmation_mixin.py` serializes concurrent `ask_user` calls.
  - `BufferedUI` for sub-agents (output buffered until flush/approval/completion).
  - Main agent output buffered during parallel operations; parallel agent approvals wait for user action.

- **Improvement: Dynamic, permission-filtered tool descriptions**:
  - `DelegateToAgent`'s agent roster is filtered by the active policy at render time.
  - No policy → full roster, byte-identical to before.

- **Improvement: Permission examples**:
  - `examples/permission-policy/` with `zrb_init.py` demonstrating `allow`, `deny`, and `ask` rules with arg patterns.

- **Chore: Removed redundant tools and `read_bool`**:
  - `tool/read_bool.py` removed (functionality subsumed by `ask_user_question`).
  - Dead/duplicate tool entries cleaned up.

- **Documentation: ADRs for permission, plan mode, truncation, background agents, approval precedence**:
  - `docs/adr/07-llm-extension.md`: ADR-0049 (capability tags), ADR-0050 (permission rulesets), ADR-0051 (plan mode), ADR-0052 (truncation backstop), ADR-0053 (filtered tool descriptions), ADR-0054 (background subagents), ADR-0055 (approval precedence), ADR-0056 (Shell as primary execution tool).

- **Tests**:
  - New: `test/llm/permission/test_capability.py`, `test_policy.py`, `test_state_and_gate.py`.
  - New: `test/llm/tool/test_plan_mode.py`, `test_shell.py`, `test_shell_background.py`, `test_delegate_background.py`.
  - New: `test/llm/agent/test_agent_truncate.py`.
  - New: `test/config/test_env_field.py`.
  - New: `test/llm/test_factory_resolver.py`.
  - Extended: `test/llm/tool/test_bash.py` (alias), `test_delegate_tool.py` (permission filtering), `test_plan.py`.
  - Extended: `test/llm/ui/base/test_commands_mixin.py`, `test/llm/ui/default/test_confirmation_mixin.py`, `test_keybindings_mixin.py`, `test/llm/ui/test_ui.py`.

## 2.31.0 (May 29, 2026)

- **Feature: Command lifecycle hooks (`PreCommand` / `PostCommand`)**:
  - Two new `HookEvent` members (`hook/types.py`) fire in the interactive chat TUI when the user runs a command. `PreCommand` fires before the command runs and **can block it** (exit code 2 / `{"decision":"block"}` / `deny`); `PostCommand` fires after a recognized command completes. Plain chat messages do not fire these events.
  - **`PreCommand` can rewrite a command's argument on the fly** by returning a `command_args` value (Python `HookResult(modifications={"command_args": ...})`, or `{"command_args": ...}` JSON from a shell hook). The command token is preserved, the argument swapped — e.g. transparently downgrade `/model opus` to `/model sonnet`. Highest-priority hook wins.
  - `HookContext` gained `command_name` / `command_args` / `command_handled` (`hook/interface.py`), surfaced to shell command-hooks as `CLAUDE_COMMAND_NAME` / `CLAUDE_COMMAND_ARGS` env vars (`hook/hook_creators.py`).
  - Command dispatch is **recognition-based, not prefix-based**: `commands_mixin.py` gained `classify_input` + a single-source `_command_table` so any configured token routes correctly — built-ins (`/save`, `/exit`), a user-configured `>` redirect, and skill slash-commands (`/debug`, …) all fire the hooks; tokens need not start with `/`. Model-driven skill activation continues to fire `PreToolUse` (`ActivateSkill`).
  - Dispatch now runs as a background task (required for the async hook pipeline), serialized by an in-flight guard so a second command can't race a prior `/save`/`/load`/`/exit`; run-while-thinking commands (`/btw`, YOLO toggle, incl. selective `/yolo Write,Edit`) are exempt and run independently, as before.

- **Feature: `AskUserQuestion` tool + interactive mode**:
  - New `ask_user_question` tool (`tool/ask.py`, LLM-visible name `AskUserQuestion`) lets the model pose structured multiple-choice questions mid-turn and read the answers. Use it only when a choice is non-obvious and the wrong pick wastes significant work.
  - Interactive state flows through an `interactive_mode` `ContextVar` set by `system_context` from `ctx.input.interactive`. In non-interactive runs (`zrb llm chat --interactive false`) the tool short-circuits with a `[SYSTEM SUGGESTION]` instead of blocking on stdin; the System Context block advertises availability.

- **Bug Fix: `Grep` tool parameter renamed `regex` → `pattern`**:
  - `search_files` (`file_search.py`) exposed its first argument as `regex`, but the tool is named `Grep` — and the model's strong prior (Claude Code's `Grep`, and zrb's own `Glob`) is a `pattern` argument. Agents called `Grep(pattern=...)`, which failed schema validation. The parameter is now `pattern`; the docstring disambiguates it from `Glob` ("a regular expression, NOT a glob"). All callers used positional args, so nothing else changed.

- **Improvement: Prompt and guidance consistency**:
  - `journal_mandate.md`: switched from `[[wikilinks]]` to standard markdown links plus a `## Backlinks` section, matching `core-journaling` and the `journal-lint` tool (which only recognizes markdown links). `activity-entry.md` template fixed likewise.
  - `core-research.md` / `research` skill: corrected a dangling reference (the non-existent "Task Handling" rule → the Working Loop's Frame step) and dropped a `DelegateToAgent` mention that doesn't apply when the skill runs in a no-delegate sub-agent.
  - `git_mandate.md`: documented that worktree creation (`EnterWorktree`) is exempt from the git approval gate (it builds an isolated tree without touching the current tree/index/branches).
  - `common_tools.py`: added an `UpdateTodo` guidance entry (and moved the "one status change per call" rule onto it); corrected the misleading delegate-guidance comment. "Journaling Protocol" → "Journal Protocol" naming unified.

- **Chore: Version bumped to 2.31.0**:
  - `pyproject.toml`: `2.30.2a1` → `2.31.0`.

- **Tests**:
  - New: `test/llm/tool/test_ask.py` (217 lines), `test/llm/tool/test_ambient_state.py`.
  - Extended: `test_commands_mixin.py` and `test_keybindings_mixin.py` (command classification, dispatch, blocking, arg-rewrite, in-flight guard, plus end-to-end integration tests driving the real keybinding with configured tokens incl. `>`); `test_hook_manager.py` (command env injection); `test_interface.py` (command context fields); `test_file.py` (`Grep` `pattern` keyword); `test_system_context.py` / `test_base_ui.py` (interactive mode, blocking hook execution).

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)
