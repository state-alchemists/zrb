🔖 [Documentation Home](../README.md)

## 2.32.2 (June 6, 2026)

_Cumulative summary of the 2.32.1–2.32.2 patch line._

- **Feature: `include_hidden` parameter for `LS` and `Glob` tools**:
  - `list_files` (`LS`) and `glob_files` (`Glob`) accept an optional `include_hidden: bool = False`. When `True`, dotfiles and dot-directories are surfaced instead of skipped — while still honoring `exclude_patterns`, so `.git`/`node_modules` remain excluded by default. `glob_files` also passes the flag through to `glob.glob()`. Default `False` preserves backward compatibility (`llm/tool/file_list.py`).

- **Fix: orphaned LSP subprocesses and hook-executor threads at process exit**:
  - Interactive chat sessions leaked two process-global resources at shutdown: mid-chat LSP language-server subprocesses (only the one-off `analyze_code` tore down its own) and the hook executor's non-daemon worker threads (which could keep the interpreter alive). A two-tier cleanup closes both — a graceful in-loop `_teardown_interactive_resources()` (`shutdown_all()` on LSP servers + `shutdown_hook_executor(wait=False)`), gated to the interactive path so the web/SSE runner isn't disrupted, plus an `atexit` backstop `LSPManager.force_kill_all()` that `SIGKILL`s any survivor whose event loop is already closed. Both are idempotent once the graceful path runs.

- **Tests**: `include_hidden` coverage in `test/llm/tool/test_file.py`; `force_kill_all` coverage in `test/llm/lsp/manager/test_lsp_manager.py`.

## 2.32.0 (June 5, 2026)

_Cumulative summary of the 2.32.0 line (`2.32.0a1`–`2.32.0b5` pre-releases consolidated). 3149 tests passing at 90.40% coverage._

- **Feature: permission policy system, plan mode, and approval precedence**:
  - New `zrb/llm/permission/` package: capability tags (`READ`, `EDIT`, `EXECUTE`, `NETWORK`, `DELEGATE`, `META`), ordered first-match-wins `Rule`s with `allow`/`ask`/`deny` actions + `arg_pattern` globs, and `current_permission_policy` / `current_agent_mode` `ContextVar`s. Tools are tagged centrally in `common_tools.py`; `yolo` is re-expressed as a `PermissionPolicy` via `from_yolo()`.
  - Plan mode (`EnterPlanMode`/`ExitPlanMode`, tagged `META`) is a preset read-only policy (READ/NETWORK/META allow, EDIT/EXECUTE/DELEGATE deny), enforced by the execution gate in `agent/common.py`.
  - A single approval precedence chain — `permission_policy → tool_policy → yolo` — where `deny` stops at the gate and `allow` bypasses lower checks. `DelegateToAgent`'s roster is filtered by the active policy at render time. ADR-0049–0053, 0055.

- **Feature: `Shell` as primary execution tool + background agents**:
  - New `shell.py` (`run_shell_command`, streaming stdout/stderr, configurable truncation/timeout) replaces `Bash`, which becomes a thin backward-compat alias; `shell_background.py` adds non-blocking execution with a polling handle.
  - Background subagents (`DelegateToAgentBackground` + `GetDelegationResult`) spawn detached `asyncio` tasks that inherit the parent policy and route approvals to the parent UI's confirmation queue (no deadlocks, no silent auto-approve); multiple can run in parallel.
  - Tool-output truncation backstop: a global `LLM_MAX_TOOL_RESULT_CHARS` cap (default 100k) truncates model-facing `content` (head+tail with re-fetch hint) while preserving structured `return_value`. ADR-0054, 0056, 0052.

- **Feature: interactive UX**:
  - `/model` gained `small <name>` and `multimodal <name>` subcommands (with tab-completion); summarizer agents are recreated per call so changes take effect immediately.
  - Todo progress visualization: `write_todos`/`update_todo`/`clear_todos` push a styled progress card to the active UI (TUI, StdUI, web SSE `todo_progress` kind) after every change. ADR-0057.
  - Confirmation queue serializes concurrent `ask_user` calls; `BufferedUI` buffers sub-agent output until flush/approval/completion.

- **Improvement: config system & LSP preference**:
  - New `EnvField` data descriptor replaces 700+ lines of getter/setter/cast boilerplate across all config mixins; `contextvars.py` becomes the canonical index of every `ContextVar`. Config mixins gained `TYPE_CHECKING` `Protocol` host-classes for static attribute checking.
  - New `ZRB_LLM_LSP_PREFERRED_SERVERS` (ordered, comma-separated) lets the agent prefer specific LSP servers when several match a file; `LSPManager.get_server` defaults to it.

- **Reliability: LLM history, summarizer, and agent correctness**:
  - New empty-completion guard regenerates blank / leaked `"(tool call)"` completions instead of surfacing them, and `filter_nil_content` no longer injects the `"(tool call)"` placeholder into tool-call-only turns (which weak models had learned to imitate). ADR-0059.
  - Fixed a deferred-tool summarizer death-spiral (`UserError` retry loop) by clearing stale `current_results` and skipping the summarizer between deferred-tool iterations. ADR-0058.
  - Fixed `_merge_consecutive_messages` mutating cached history in place; history-file corruption recovery preserves unknown fields; `create_agent` gained `resolve_model=False` to stop model-callback double-firing; the OpenAI `content:null` patch verifies its target and warns on pydantic-ai drift.
  - Summarization calls retry transient 5xx/429 errors and use targeted `strip_orphaned_returns` instead of wholesale sanitization; tiktoken failures are caught broadly; tool error paths carry a `[SYSTEM SUGGESTION]` prefix; message placeholders centralized as constants.

- **Security: web authentication hardening**:
  - The access path requires the JWT `type == "access"` claim (a refresh token can no longer be used as an access token); auth cookies are issued `Secure` + `SameSite=Lax` (plus `HttpOnly`); `is_password_match` uses constant-time `secrets.compare_digest`; `run_zrb_task` `shlex.quote`s each argument against shell injection.

- **Fix: task-engine & infrastructure correctness**:
  - Signal-killed processes (negative return code) are now treated as failure; `readiness_checks` memoizes its default check task; `tcp_check`/`http_check` no longer leak sockets or block the event loop; deferred coroutines are cancelled on session `terminate()`; a sweep replaced mutable default arguments with `None` sentinels.
  - `LspRenameSymbol(dry_run=False)` actually writes the edit and reports an honest `applied` flag; web search reflects the requested page and survives empty Brave snippets; a configured limiter of `0` now blocks; concurrent SSE chat sessions no longer clobber each other's UI/approval/history wiring (`ChatSessionManager.task_lock`).

- **Refactor: encapsulation & UI decomposition**:
  - `BaseUI` and the command-dispatch file were split into cohesive mixins (`HistoryReplayMixin`, `SystemInfoMixin`, `ConversationCommandsMixin`, `ModelCommandsMixin`, `ExecCommandsMixin`) with no behavior change (ADR-0060). Cross-module private access was replaced with public accessors/properties on `BaseTask`, `BaseUI`, `MultiUI`, and the hook manager. Run-scoped `ContextVar`s bind through an `ExitStack` for symmetric set/reset; deprecated `get_event_loop().create_task` calls were modernized.

- **Improvement: prompts, skills, and documentation**:
  - Refined `persona`/`mandate`/`journal_mandate` (conciseness, "ask rather than guess", activity-vs-insight journaling, new insight-note template); made the skill catalogue prompt more authoritative; removed the now-redundant `read_bool` tool. Large docs/example accuracy sweeps fixed constructor signatures, env-var defaults, import paths, and broken snippets across the guide and `examples/`.

- **CI & tests**:
  - Added `.github/workflows/test.yml` (flake8 `F` + full pytest with coverage on Python 3.11–3.13) and a hermetic `test/conftest.py` (deterministic env defaults + per-test `os.environ` snapshot/restore); `zrb-test.sh` enforces `--cov-fail-under=90` on full runs.

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


## 2.30.2a1 (May 28, 2026)
_Cumulative summary of the 2.30.1–2.30.2a1 patch line._

> Pre-release: 2.30.2a1 is an alpha.

- **Feature: Post-write/post-edit diagnostics**:
  - New `src/zrb/llm/tool/post_write_check.py`: `format_post_write_diagnostics()` runs `ast.parse` + `pyflakes` on Python files after Write/Edit tool calls, surfacing syntax errors and undefined names inline in the tool result. Non-Python files and error-free files produce no output.
  - `write_file()` (`file_write.py`) and `replace_in_file()` (`file_edit.py`) became `async` and append a `[DIAGNOSTIC]` section to their return value when errors are detected — the model sees errors immediately and can fix them in the same turn.

- **Feature: LSP push-diagnostics plumbing**:
  - `LSPServer` (`lsp/server.py`) gained `did_open_text_document()` and `did_change_text_document()` with full `didOpen`/`didChange` state tracking per URI. `get_diagnostics()` now synchronizes the file with the server via `didOpen`/`didChange`, then polls for `textDocument/publishDiagnostics` push notifications (50ms interval, 1.5s timeout), falling back to LSP 3.17 pull-diagnostics. Incoming `publishDiagnostics` notifications are cached in `self._diagnostics`.

- **Feature: Installer LSP server setup**:
  - `install.sh` and `install.ps1` both gained `install_lsps()`: installs `python-lsp-server[all]` unconditionally, then optionally installs `typescript-language-server` (JS/TS), `gopls` (Go), and `rust-analyzer` (Rust) when their toolchains are present. Users are prompted during installation.

- **Improvement: Prompt and tool guidance deduplication**:
  - `common_tools.py`: Redundant tool guidance entries removed — Read's `old_text` note, Write's overwrite warning, Edit's read-first rule, Grep's truncation note — these are already documented in the tool docstrings themselves.
  - `lsp/tools.py`: MANDATES sections removed from all 8 LSP tool docstrings. The usage rules remain in `tool_guidance.py` (the single source of truth).
  - `rag.py`: MANDATES removed from RAG tool docstring; replaced with a one-line usage instruction.
  - `tool_guidance.py`: Parallel-tool-call sections rewritten in plain language — no emoji, no ALL-CAPS, no concatenated-tool-name examples. Heading normalized to `## Tool Call Parallelism` for both supported and unsupported models.

- **Improvement: Mandate.md strengthened**:
  - "Completeness" now explicitly requires deliverable files to land on disk via a Write or Edit tool call — printing content into chat, even in a fenced block, does not count.
  - Destructive action rule expanded: `package downgrades`, `CI/CD changes`, `posts to Slack/email/PRs` added. New clause: investigate unfamiliar state (unexpected files, branches, stashes, lock files) before destroying — `--no-verify`, `rm -rf`, `git reset --hard` are not shortcuts.
  - Scope rule promoted above Memory (priority 6 → 5). Added scope-scoping rules: approved edit to file X ≠ approval to refactor file Y; approval is one-shot per action.
  - Understand step: hypothesis threshold softened from "3+ tool calls" to "two distinct hypotheses failed".
  - Plan step: explicitly states it describes *what changes where*, not a preamble.
  - Execute step: broken into sub-bullets; `DelegateToAgent` gate removed (moved to tool guidance).

- **Improvement: Persona.md tightened**:
  - Removed "Your context window is a budget" line (covered by mandate completeness rule).
  - Source citation format expanded: `file:line-range` and `file:symbol` added alongside existing `file:line`.

- **Improvement: Tool docstring refinements**:
  - `file_edit.py`: `replace_in_file()` gained a docstring documenting the post-edit validity requirement: if the change would leave the file malformed (broken indent, missing import, dangling brace), the caller should widen `old_text` or use Write to re-emit the whole file.
  - `file_rm.py`: Clarified irreversibility ("there is no trash; the bytes are gone").
  - `file_mv.py`: Added overwrite warning and path-confirmation guidance.
  - `file_search.py`: Uses "regex" instead of "pattern" in no-match message.
  - `worktree.py`: Entry message simplifies to path + branch only; exit message clarifies `keep_branch=False` is irreversible.
  - `delegate.py`: Worktree line in sub-agent envelope shortened.

- **Improvement: System context token-limit line removed**:
  - `system_context.py`: Token-limit-per-request line removed, dropping the `CFG` import. Token limits are model-specific; the model itself already knows its own context window.

- **Chore: LLM challenges extracted to separate repo**:
  - `llm-challenges/` directory removed from the zrb repository. The evaluation framework (challenge definitions, experiment data, results, report) now lives in its own repository.

- **Documentation: Changelog history backfilled**:
  - `docs/changelog-v2.md`: Added changelog entries for versions 2.28.0 through 2.28.6 — these were previously omitted from the v2 changelog.

## 2.30.0 (May 24, 2026)

- **Breaking: `DelegateToAgent` / `DelegateToAgentsParallel` signature change**:
  - `delegate_to_agent` now requires `deliverable: str` and `non_goals: list[str]` in addition to `agent_name` and `task`. The parallel variant requires the same keys per task dict; missing keys short-circuit with a clear schema error before any sub-agent runs.
  - Sub-agent messages are now wrapped in a structured envelope (`DELIVERABLE` / `NON-GOALS` / `TASK` / `CONTEXT` / `BEFORE RETURNING`) so the scope clamp is the first thing the sub-agent reads, not free-form context.
  - Rationale: with the previous free-form `task` arg, parent agents passed fuzzy specs and sub-agents over-produced. The required fields force the parent to articulate the deliverable and adjacent work to avoid; schema is enforcement, prompt rules were not.
  - Migration: any custom code calling `delegate_to_agent(agent_name, task, ...)` positionally must add `deliverable` and `non_goals`. Pass `non_goals=[]` only when scope expansion is genuinely impossible.

- **Improvement: Delegation tool guidance rewritten**:
  - `common_tools.py` `DelegateToAgent` / `DelegateToAgentsParallel` `ToolGuidance` entries reframed affirmatively ("Delegate only when ALL apply…") with a fidelity rationale replacing the previous context-budget rationale.
  - `mandate.md` Working Loop step 4 gained a one-sentence delegation gate so the whether-to-delegate decision lives in the same MECE section as the rest of execution discipline.

- **Improvement: AGENTS.md restructured**:
  - Project structure tables condensed into prose (was 175 lines of tables, now ~98 lines of concise bulleted walkthrough). Core Framework, LLM Integration, and Test Locations tables replaced with self-describing `ls src/zrb/` guidance plus per-module docstrings as the source of truth. Key Task Types table simplified.
  - LLM Prompt System section rewritten with MECE section semantics, ContextVar reference pointing to `src/zrb/contextvars.py`, and new lazy-import policy documentation.

- **Feature: `custom_command/resolver.py`**:
  - Command resolution extracted from `custom_command/__init__.py` into its own module. No behavior change — cleaner module boundary.

- **Feature: `BaseUI` extracted in `ui/base/ui.py`**:
  - New base class (+107 lines) factors shared UI logic out of `commands_mixin.py`. `MultiUI` support added (+10 lines). Reduces `commands_mixin.py` by ~47 lines.

- **Improvement: Prompts overhauled**:
  - `persona.md`, `mandate.md`, `journal_mandate.md` — tightened, deduplicated, softened rigid phrasing (cue-framing replaces hard prohibitions). Consistent with the 2.28.2a1 mandate refactor pass.

- **Improvement: History formatter refinements**:
  - `history_formatter.py`: format stability improvements for multi-turn conversations.
  - `runner_mixin.py`: Better retry handling when skill is passed as a message parameter.

- **Improvement: Sub-agent manager improvements**:
  - `loader_mixin.py`: New `_load_*` helpers (+16 lines) for cleaner skill/plugin resolution.
  - `manager.py`: Tool registration and delegation flow streamlined (+75/−?).

- **Improvement: Tool refinements**:
  - `bash.py`: Better error messaging for failed commands.
  - `file_read.py`: Improved path validation for edge cases.

- **Improvement: Agent skill definitions**:
  - `code-reviewer.agent.md`, `generalist.agent.md`, `researcher.agent.md` — each gained `disable-model-invocation: true` so they only fire when the user explicitly calls `/delegate-to`.

- **Bug Fix: Function definition removed from `custom_command/__init__.py`**:
  - Moved command resolution logic to `resolver.py` — `__init__.py` now only re-exports. Prevents accidental import cycles.

- **Bug Fix: `Claude` prompt section loading**:
  - `prompt/claude.py`: Fixed section-ordering edge case when project-context files are missing.

- **Tests**:
  - New: `test/llm/agent/subagent/test_loader_mixin.py` (52 lines), `test_subagent_manager.py` (147 lines).
  - New: `test/llm/prompt/test_claude.py` (67 lines) — project-context loading edge cases.
  - New: `test/llm/task/chat/test_runner_mixin.py` (60 lines) — runner retry/message handling.
  - New: `test/llm/ui/test_ui.py` (244 lines) — base UI and multi-UI coverage.
  - Extended: `test/llm/util/test_history_formatter.py` (+60 lines), `test_history_utils.py` (+18 lines).

- **Documentation**:
  - `AGENTS.md`: Fully restructured (see above).
  - `CLAUDE.md`: Minor update.
  - `docs/advanced-topics/maintainer-guide.md`: Updated to match the new AGENTS.md structure.

## 2.29.0 (May 22, 2026)

- **Dependency: `pydantic-ai-slim` upgraded `~1.93.0` → `~1.101.0`, now installed with the `[mcp]` extra**:
  - The `[mcp]` extra pulls `fastmcp-slim[client]>=3.3.0`, required by the new `MCPToolset`. This is a new transitive install dependency.
  - All deprecation warnings from the eight intervening minor versions are silenced — `pytest -W error::DeprecationWarning` runs clean across the suite.

- **Breaking-ish: `LLM_MODEL` default switched from `"openai:gpt-4o"` to `"openai-chat:gpt-4o"`**:
  - pydantic-ai 1.x warns that bare `openai:` will resolve to the Responses API in v2; `openai-chat:` pins the current Chat Completions behavior. Users with an explicit `LLM_MODEL` env var are unaffected. The `LLMConfig.small_model` default docstring was updated similarly.
  - Completion-fallback known-model list in `llm/app/completion/completer.py` likewise refreshed: `openai:` → `openai-chat:`, `google-vertex:` → `google-cloud:` (per pydantic-ai's provider rename in #5336).

- **Breaking-ish: `load_mcp_config()` now returns `pydantic_ai.mcp.MCPToolset` instances**:
  - `src/zrb/llm/tool/mcp.py` rewritten to use `MCPToolset` + `fastmcp.client.transports.StdioTransport` instead of the deprecated `MCPServerStdio` / `MCPServerSSE`. Behavior preserved (no automatic tool-name prefixing, same env-var expansion syntax). `_expand_env_vars` reimplemented locally so zrb no longer depends on a private `pydantic_ai.mcp._expand_env_vars` symbol.

- **Deprecation cleanup (pydantic-ai 1.x → v2 prep)**:
  - `Agent(tool_retries=N)` → `Agent(retries={"tools": N})` in `llm/agent/common.py` (per pydantic-ai #5500).
  - `event.result.usage()` → `event.result.usage` in `llm/util/stream_response.py` (method-style usage accessor deprecated in #5263).
  - `pydantic_ai.messages.BuiltinTool*Part` → `NativeTool*Part` references in `llm/agent/run/history_utils.py` (per the built-in → native tools rename in #5338).
  - `HistoryProcessor` type-hint import moved off the internal `pydantic_ai._agent_graph` path. The type alias has no public re-export in v1.101, so zrb now defines its own `Callable[..., Awaitable[list[ModelMessage]]]` alias in `llm/agent/common.py` (more accurate to zrb's actual usage, which passes extra positional args at one call site) and the task modules import it from there. Removes the last `pydantic_ai._*` import from `src/zrb`.

- **Hygiene: `zrb.util.todo` re-export shim trimmed**:
  - Removed cargo-cult `read_file, write_file` re-export (no patches targeting `zrb.util.todo.read_file`/`.write_file` in tree, no external callers).
  - Removed `_parse_date` and `_get_minimum_width` from the re-exports — private symbols had no external callers.
  - Replaced bare `# noqa: F401` markers with an explicit `__all__` so the re-export contract is documented. Callers reaching for these names through `zrb.util.todo` are unaffected; anything importing the removed names should switch to `zrb.util.todo_parser` / `zrb.util.todo_render` / `zrb.util.file` directly.

- **Hygiene: AGENTS.md `# lazy:` import-comment sweep**:
  - 145 in-function imports across 81 files now carry the `# lazy: <reason>` justification comment mandated by AGENTS.md. Two stock reasons used: `# lazy: heavy third-party` (pydantic_ai, fastapi, prompt_toolkit, mcp, etc.) and `# lazy: zrb internal (heavy via transitive / circular)` for `zrb.*` imports. Behavior unchanged — the imports were already lazy; only the comments were missing.

- **Tests**:
  - `test/llm/tool/test_mcp.py` rewritten to assert against `MCPToolset` + `StdioTransport` instead of `MCPServerStdio` / `MCPServerSSE`.
  - `test/llm/agent/test_common.py`, `test/llm/util/test_stream_response.py`, `test/llm/agent/run/test_history_utils.py`, `test/llm/agent/run/test_runner.py` updated to match the deprecation cleanup above.
  - Full suite: 2819 passing, no deprecation warnings.

## 2.28.6 (May 22, 2026)

_Cumulative summary of the 2.28.1–2.28.6 patch line._

- **Feature: Per-model capability registry (`zrb.llm.util.capabilities`)**:
  - New `ModelCapabilityRegistry` with `model_capabilities` singleton tracking image/audio/video input and tri-state `supports_parallel_tool_calls` per model, with field names following LiteLLM conventions.
  - Built-in pattern table covers GPT-4o/4.1/5, Claude 3/4, Gemini, Llava, Pixtral, plus deny entries for `minimax-m2.7` and `glm-4.7`, which emit malformed concatenated tool calls when batching.
  - User-extensible via `model_capabilities.register("pattern", **overrides)` from `zrb_init.py`; `create_agent()` consults it and injects `parallel_tool_calls=False` for known-malforming models (caller settings always win).
  - Replaced the internal `modality.py`; `multimodal_describe.py` now uses `model_capabilities.supports_modality(...)`.

- **Refactoring: Consolidated tool/guidance registration into `apply_common_tools()`**:
  - New `src/zrb/llm/common_tools.py` exposes `apply_common_tools(host)` and a `CommonToolHost` Protocol satisfied by `LLMChatTask`, `LLMTask`, and `SubAgentManager`, registering shipped default tools, the MCP toolset factory, static and dynamic tool guidance, and the model-aware parallel-tool-call section factory.
  - `builtin/llm/chat.py` shrank from 440 to 152 lines by delegating to `apply_common_tools`; `SubAgentManager` now calls it, and the duplicated `subagent/default_tools.py` was deleted.
  - `LLMTask` gained `add_tool_guidance_factory()` and `add_tool_guidance_section_factory()` (matching the other hosts) so programmatic users can register dynamic guidance.
  - Tool imports inside `apply_common_tools` are lazy and sourced from submodules to avoid the `delegate.py` → `subagent.manager` circular-load cycle.

- **Improvement: Prompt mandate refinements**:
  - Journal mandate tightened to "created significant decision" and gained a "Why 'before reply'?" rationale (a finding not logged before replying is lost).
  - Mandate refactored for MECE; post-activation and communication directives softened from hard prohibitions to cue-framing (hard wording triggered aggressive batching in weaker models like glm-4.7), and the parallelize rule reworded to favor correctness over batching where the runtime doesn't support multiple calls.
  - Added production-readiness rules: completion requires producing the expected output, run generated code to verify, meet all stated criteria, and a refined "repeated failures" recovery that catches re-running unchanged commands 3+ times.

- **Improvement: Invalid-tool-call retry messaging**:
  - The corrective message for invalid tool names now addresses both invented names and concatenations (e.g. `ReadRead`), instructing the model to emit exactly one tool call per response.

- **Security Fix: `idna` bumped to `>=3.15` (GHSA-65pc-fj4g-8rjx / CVE-2026-45409)**:
  - `idna<3.15` is vulnerable to a DoS via crafted inputs hitting `valid_contexto` before length validation; it is transitive via `requests`, `httpx`, and `anyio`. Added an explicit floor in `pyproject.toml` and updated the lockfile from `3.11` to `3.15`.

- **Improvement: LLM chat TUI touch-ups**:
  - Shrank the input-frame title to a compact key reference and moved the full reference under `/help` (or `/info`), which now includes a "Keyboard Shortcuts" section and renders custom commands' `description`.
  - `create_banner()` accepts `max_width` and drops the ASCII logo when it would overflow narrow terminals, wired to the live terminal width.
  - Help-text descriptions gained `max_length` truncation (rendered at `max_length=75`) to prevent welcome-banner overflow.

- **Bug Fix: `[build-system]` typo in `pyproject.toml`**:
  - Renamed the `build-system` key to `build-backend` per PEP 517, fixing a `BuildSystemTableValidationError` on install via Poetry/pip.

## 2.28.0 (May 15, 2026)

- **Breaking: `PromptManager` simplified to single `include_sections` param**:
  - `PromptManager.__init__()`: 9 individual `include_*` boolean flags (`include_persona`, `include_mandate`, `include_git_mandate`, `include_system_context`, `include_journal_mandate`, `include_claude_skills`, `include_cli_skills`, `include_project_context`, `include_tool_guidance`) replaced by a single `include_sections: list[str] | None` parameter. All 9 corresponding properties removed.
  - New `CFG.LLM_INCLUDE_SECTIONS` config list drives prompt section composition by default; instance-level `include_sections` override wins.
  - Removed from `zrb.llm.prompt`: `get_persona_prompt()`, `get_mandate_prompt()`, `get_git_mandate_prompt()`, `get_journal_prompt()`, `get_summarizer_system_prompt()`, `get_file_extractor_system_prompt()`, `get_repo_extractor_system_prompt()`, `get_repo_summarizer_system_prompt()`, `create_cli_skills_prompt()`. Consolidated into `get_prompt(name, **extra_replacements)`.
  - Removed `zrb.llm.prompt.cli` module (`create_cli_skills_prompt`).
  - Removed `chat_tool_policy.py` support for batch `paths`/`files` approval (WriteMany).

- **Breaking: ReadMany/WriteMany batch tools removed**:
  - Removed `read_files`, `write_files` tool functions, `WriteMany`/`ReadMany` auto-approve policies, `write_files_formatter`, and `read_files_validation_policy`. `Read`/`Write` handles multiple files via parallel calls or chunked writes.
  - `docs/advanced-topics/llm-integration.md` updated to remove `ReadMany`/`WriteMany` from the tools table.

- **Breaking: Tool-call internals trimmed**:
  - Removed `tool_call/argument_formatter/write_file_formatter.py` and `tool_call/tool_policy/read_files_validation.py`.
  - `zrb.llm.tool_call` exports reduced accordingly.

- **Feature: History retention + backup rotation**:
  - New `_retry_prompt_to_text()` helper; history sanitization now gated behind `DEBUG` logging for performance.
  - New `_safe_int_from_env()` helper in `LLMContentMixin` deduplicates `int(get_env(...))` pattern across 5 properties.
  - New `CFG.LLM_HISTORY_BACKUP_RETAIN` (default `3`) controls how many timestamped backups are kept per conversation. Set to `-1` to keep all (legacy behavior) or `0` to disable backups.
  - `file_history_manager.py`: Backup rotation now sorts by filename (lexicographic = chronological for ISO-8601 timestamps) instead of mtime — deterministic on coarse filesystems (FAT32, Docker overlayfs).
  - `snapshot/manager.py`: Cached file loading (`_load_file_content_cached`, `_get_search_directories_cached`). New incremental sync mode that skips per-file copies when the destination already matches by size/mtime — safe for workdir→shadow direction only.

- **Feature: Read/LS/Glob/Grep auto-approved on skill and plugin directories**:
  - New `approve_if_path_inside_skill_or_plugin_dir` predicate that resolves all skill search directories (builtin, home, project, extras) via `SkillManager.get_search_directories()` and explicit `CFG.LLM_PLUGIN_DIRS` at call time — respects programmatic overrides.
  - Registered in `chat.py` for `Read`, `LS`, `Glob`, `Grep`, `AnalyzeFile`.

- **Feature: YOLO mode propagated to sub-agents**:
  - `yolo.py`: `make_yolo_inheritance_checker()` now handles `frozenset` (selective YOLO) — when the parent has selective YOLO enabled, only the named tools are auto-approved in sub-agents. Previously selective YOLO degraded to full YOLO in sub-agents.
  - `delegate.py`: Added `yolo` property to `BufferedUI` that delegates to the wrapped parent UI, so `check_yolo_inheritance`'s UI fallback works through the buffered wrapper.

- **Feature: Escape cancellation preserves conversation history**:
  - When pressing Escape to cancel an LLM response, the user's message and a `[SYSTEM: Response was interrupted by user]` marker are now saved to conversation history. The next turn builds on the interrupted context instead of starting fresh. No changes to `runner.py` — handled entirely in `_exec_action_inner` in `llm_task.py`.

- **Improvement: Project-context file reading cached**:
  - `claude.py`: `_load_file_content` now caches reads by `(path, mtime)` so per-turn AGENTS.md/CLAUDE.md re-reads cost only a stat call. `_get_search_directories` also cached per `(home, cwd)` pair.
  - Fixed `break` → `continue` in `create_project_context_prompt` — was skipping all doc files after README; now correctly continues to remaining files.

- **Improvement: File tool error handling**:
  - `file_read.py`, `file_edit.py`, `file_search.py`: Better path validation, fuzzy matching helpers (`_find_fuzzy_match`, `_match_line_trimmed`), indentation-flexible matching (`_match_indentation_flexible`).

- **Improvement: `assistant_name` check tightened**:
  - `manager.py`: `if assistant_name` → `if assistant_name is not None` so empty string `""` is no longer replaced by `CFG.LLM_ASSISTANT_NAME`.

- **Chore: Removed dead exports** — `tool/__init__.py` and `tool_call/__init__.py` cleaned up, unused `default_tools.py` tool removals.

## 2.27.1 (May 14, 2026)

- **Refactoring: Shared filesystem-scanning utilities extracted**:
  - New `src/zrb/util/asset_scanner.py` exposes `scan_files(directory, max_depth, on_file_found, ignore_dirs)` and a module-level `IGNORE_DIRS` constant (`.git`, `node_modules`, `__pycache__`, `venv`, `dist`, `build`, `htmlcov`). Replaces the duplicated `_scan_dir` / `_scan_dir_recursive` pattern that previously lived in both `llm/skill/manager.py` and `llm/agent/subagent/manager/loader_mixin.py`. Silently swallows `PermissionError`/`OSError` so one inaccessible branch never aborts a full scan.
  - New `src/zrb/util/dir_search.py` exposes `get_upward_dirs(start_dir)` (root → cwd traversal for multi-tier project-config discovery) and `scan_plugin_dirs(plugins_root)` (returns plugin dirs containing a `.claude-plugin/plugin.json` manifest). Shared by the skill loader and the hook loader so the "user home → project dirs → plugins → builtin" discovery order has one canonical implementation.
  - `llm/skill/manager.py` and `llm/agent/subagent/manager/loader_mixin.py` switched to `scan_files()` + `_on_file_found` callbacks; private `_IGNORE_DIRS` removed in favour of `asset_scanner.IGNORE_DIRS`.

- **Refactoring: `hook_loader.get_search_directories()` decomposed**:
  - One monolithic function split into `_get_plugin_hook_dirs`, `_get_home_hook_dirs`, `_get_project_hook_dirs`, `_get_custom_hook_dirs` + a shared `_collect_hook_paths(base_dir)` helper. Eliminates the repeated Claude-style/Zrb-style path-building blocks for each discovery tier.
  - New `_zrb_dir_name()` helper evaluates `f".{CFG.ROOT_GROUP_NAME}"` lazily to dodge CFG init-ordering issues.
  - Priority order now documented in the module docstring (high → low): plugins → user-home config → project dirs → `CFG.HOOKS_DIRS`.

- **Refactoring: `file_search` output assembly deduplicated**:
  - New helpers in `llm/tool/file_search.py`: `_build_file_match_entry`, `_count_actual_matches`, `_truncate_file_results`, `_build_search_output`. The ripgrep path and the `os.walk` fallback path now share final result-dict assembly (results / summary / truncation notice / warning), eliminating divergent code that had grown different no-match messaging and truncation behaviour.

- **Refactoring: `CLIStyleLexer` color tables hoisted**:
  - `llm/app/lexer.py`: `_STANDARD_FG` / `_BRIGHT_FG` color tables and the `_build_style(attrs, fg, bg)` composer promoted from nested closure to module-level constants. `lex_document` now declares its state as `attrs` / `fg` / `bg` (was `current_*`) for readability. Added a class docstring enumerating supported ANSI features (bold/faint/italic/underline; 8 std + 8 bright FG/BG; 24-bit RGB `38;2;R;G;B`; 256-color palette `38;5;N`; state persistence across lines).

- **Refactoring: Long-method decomposition across LLM internals**:
  - `llm/prompt/manager.py`, `llm/snapshot/manager.py`, `llm/task/chat/runner_mixin.py`, `llm/history_manager/file_history_manager.py`, `llm/hook/interface.py`, `llm/message.py`, `llm/tool/plan.py`, `llm/agent/subagent/manager/manager.py`, `llm/agent/subagent/manager/search_mixin.py`, and `task/base/monitoring.py` all received internal restructurings — extracting helpers from oversized methods, grouping related methods together, and tightening reorder for readability. No behavior changes.
  - `llm/skill/manager.py` lost its private `_ensure_scanned()` helper (inlined where called); `LoaderMixin._scan_dir_recursive` removed (delegated to `scan_files`).

- **Refactoring: `system_context.py` parallel git/todo collection extracted**:
  - New `_collect_git_info(todo_manager, session_name)` helper runs git commands and todo fetch in parallel via `ThreadPoolExecutor`. Lazy-imports `is_inside_git_dir` at call time (was a module-level import). Module gains a docstring documenting the three auto-injections it performs beyond environment facts (session wiring, active worktree, pending todos).

- **Improvement: Mandate (operating rules) tightened**:
  - `mandate.md` rewritten for concision: emphatic prose ("MUST", "non-negotiable") softened to direct statements; redundant explanations folded into single-line bullets; rule priority list condensed; `Engineering Standards` bullets merged (`Stay in scope`, `Avoid band-aids`, `Verification (path to finality)` consolidated into `Minimal abstractions` / `Trade-offs are explicit` / `Done = verified`). New `Recovery` section codifies the missed-skill-activation and 3-distinct-failures protocols. New "soft override" framing in rule #7 makes the precedence between project conventions (`AGENTS.md`/`CLAUDE.md`) and safety rules explicit.
  - `journal_mandate.md` condensed from ~50 lines to ~40 with the same protocol — write categories consolidated, scan/navigate guidance shortened, headings normalized to sentence case.
  - `core-coding/SKILL.md` adds one sentence directing the LLM to prefer user-provided guidelines (`CLAUDE.md`, `AGENTS.md`, custom skills, project files) over the core companion files; core companions "fill in the gaps."

- **Improvement: `AGENTS.md` deduplicated against `contextvars.py`**:
  - The inline "Ambient State" table listing every `ContextVar`, its owning module, and its wrapper was removed. `AGENTS.md` now points readers to `src/zrb/contextvars.py` as the single source of truth. Removes a synchronization point that had previously caused drift between the table and the actual code.
  - `contextvars.py` docstring updated: `AGENTS.md` no longer needs updating when the ContextVar list changes; `docs/advanced-topics/maintainer-guide.md` and `docs/advanced-topics/architecture.md` are now the only docs that mirror the count.
  - System Context section in `AGENTS.md` shortened — the long bullet list of auto-injections was moved into the `system_context.py` module docstring instead.
  - `session_state_log/` and `session_state_logger/` collapsed into one table row that explains the split (`_log` = data structures, `_logger` = persistent writer).
  - `llm/util/` row expanded to enumerate the helper modules (`attachment`, `clipboard`, `git`, `history_formatter`, `image_scale`, `modality`, `multimodal_describe`, `prompt`, `stream_response`).

- **Bug Fix: Typo `notify_throtling` → `notify_throttling`**:
  - `llm/agent/run/runner.py:_acquire_rate_limit`: inner closure name corrected. Pure rename — no behavior change.

## 2.27.0 (May 14, 2026)

- **Feature: New skill architecture — 5 core skills with companion files**:
  - Introduced 5 consolidated core skills (`core-coding`, `core-research`, `core-design`, `core-writing`, `core-journaling`) serving as methodology hubs with companion files (language guides, workflow guides, templates, tools).
  - `core-coding`: 7 language-specific companions (`python.md`, `go.md`, `java.md`, `php.md`, `ruby.md`, `rust.md`, `typescript.md`) with language conventions, idioms, and gotchas; 4 workflow companions (`testing.md`, `debug.md`, `refactor.md`, `review.md`) with detailed step-by-step methodologies.
  - `core-design`: Decision record template (`templates/decision-record.md`) for architecture decisions.
  - `core-writing`: 3 writing templates (`api-doc.md`, `commit-message.md`, `readme.md`) with AIDA/PAS/FEBC copywriting frameworks.
  - `core-journaling`: Activity log template (`templates/activity-entry.md`); journal lint tool (`tools/journal-lint.py`) for backlink validation and orphan detection.
  - `core-research`: Scope → Discover → Synthesize → Plan workflow with approval gate enforcement.

- **Feature: Skill activation table in mandate**:
  - New Skill Activation section in `mandate.md` with a domain-to-skill mapping table (Software Engineering → `core-coding`, Research → `core-research`, Design → `core-design`, Writing → `core-writing`).
  - Activation rules: auto-approved, silent, once per session per domain, skip for trivial lookups.
  - Skill override hierarchy documented: core-coding overrides Engineering Standards; core-research overrides "work autonomously" directive; core-design enforces no-implementation-during-design; core-writing overrides generic Task Handling.

- **Feature: Skill slash-commands refactored to thin delegation stubs**:
  - `/debug`, `/testing`, `/review`, `/refactor`, `/research` now delegate to the appropriate core-skill companion file instead of carrying complete workflows inline.
  - All user-invocable skills gained `disable-model-invocation: true` — only fire when the user explicitly calls the `/command`.
  - Old `research-and-plan` skill removed (replaced by `/research` + `core-research`).

- **Refactoring: Mandate (operating rules) rewritten for clarity and thoroughness**:
  - `mandate.md`: Sections reorganized — new Session Context, Tool Use, Communication sections added; Execution Loop, Engineering Discipline, Multi-Step Tasks folded into consolidated Task Handling and Engineering Standards. Rule priority elevated Quality (#3) and Skill Activation (#5); Scope moved to #6. Tiebreaker changed from "analysis > action" to "quality > shortcuts, evidence > assumptions." Added "Strategic re-evaluation" (stop after 3 failed attempts), "Verification (path to finality)" (tests + linter + type-checker + docs), and "Default to no comments" rules.
  - `persona.md`: Identity changed from "Lead Engineer" to "versatile engineer, researcher, and writer." Added "Plain text: no emojis" and "Quality bar" guidance. Response calibration now distinguishes depth by context type (lookups vs analysis vs structured docs).
  - `journal_mandate.md`: Expanded with two-write-kind system (Insight vs Activity), explicit "Always journal / Always log / Skip" categories, "How to Write" section mandating `core-journaling` activation before every write, and "How to Scan" protocol for significant turns.
  - `persona.md`: Removed redundant pre-tool-narration and post-task-summary rules (moved to Communication section in mandate).

- **Improvement: Tool guidance strings tightened**:
  - `chat.py`: All `_static_tool_guidance` entries rewritten for concision — removed redundant `when_to_use` values, shortened `key_rule` text, merged `LspFindDefinition` guidance into generic LSP guidance. Removed `SearchJournal` standalone guidance entry. Comment added: "File Operations — only non-obvious gotchas. Tool names say what they do."

- **Security: CVE-2026-45134 langsmith bump**:
  - `pyproject.toml`: langsmith pinned to `>=0.8.0` (was `>=0.7.31`) for GHSA-3644-q5cj-c5c7 — public prompt pull deserializes untrusted manifests enabling SSRF / prompt injection via attacker-controlled prompt manifests.
  - `journal-lint.py` hardened against path traversal / shell injection in the security-fix commit.

- **Bug Fix: Worktree staleness guard**:
  - `system_context.py`: If `active_wt` path no longer exists on disk, the stale worktree is cleared from ambient state (imported `set_active_worktree`). Prevents displaying a deleted worktree path in the system context.
  - Test fix: `test_worktree.py` creates the mock worktree directory with `os.makedirs` before the system context assertion.

- **Improvement: RTK.md included in project context**:
  - `claude.py`: Added `RTK.md` to the project context search filenames list, so RTK configuration is auto-included when present.

- **Test Infrastructure**: 1621 tests pass across the LLM test suite.

- **Bug Fix: `CustomCommand` dollar-sign guard suppressed args for prompts with literal `$`**:
  - `custom_command.py` removed the `"$" not in self._prompt` guard that prevented argument appending when the prompt contained any dollar sign (regex patterns, shell examples, prices) without actual placeholder variables. Skills like `Match end of line: \d+$` now correctly pass `ARGUMENTS` through.
  - Test: `test_get_prompt_literal_dollar_not_placeholder` in `test_custom_command.py`.

- **Refactoring: Shared companion-file utilities extracted**:
  - New `src/zrb/llm/skill/_util.py` holds `discover_companion_files()` (recursive `rglob`, excludes `SKILL.md`/`SKILL.py` itself) and `format_companion_file_lines()` (groups files by top-level directory). Shared across `tool/skill.py`, `skill_command_factory.py`, and `manager.py`.
  - `tool/skill.py`: Private `_get_companion_files()` replaced with the shared `discover_companion_files()` from `_util.py`.

- **Improvement: Skill activation headers clarified**:
  - `ActivateSkill` tool output (`tool/skill.py`) now shows a consistent header with "Skill activated. The following context applies:" preamble, the skill directory marked as "working directory", a note that "All file paths ... are relative to this directory.", and grouped companion file listing (previously flat `-` bullet list).
  - `SkillCommandFactory` (`skill_command_factory.py`) now prepends the same companion-file context header to skill slash-command prompts, matching the `ActivateSkill` tool behavior.
  - Companion file formatting moved from `skill.py`'s inline `- {name}` to `format_companion_file_lines()` with directory grouping (e.g. `scripts/` → `setup.sh`, `run.sh`).

- **Documentation: "Companion Files" section added**:
  - `docs/advanced-topics/claude-compatibility.md` documents the `SKILL.md`/`SKILL.py` directory convention, companion-file auto-discovery, and example directory structure. Linked from the `ActivateSkill` tool description in the skill authoring guide.

- **Test Infrastructure: `Skill` mock attribute coverage**:
  - `companion_files` attribute added to `Skill` mocks in `test_skill.py` (2 tests) and `test_skill_command_factory.py` (3 tests) to match the new `Skill` class interface.
  - New `test/llm/skill/test__util.py`: 8 tests covering `discover_companion_files` (flat file, SKILL.md, SKILL.py, missing directory) and `format_companion_file_lines` (empty, standalone, grouped, mixed).

## 2.26.8 (May 13, 2026)
_Cumulative summary of the 2.26.1–2.26.8 patch line._

- **Reliability: Robust LLM error handling and retries**:
  - Added a provider-agnostic opaque-400 retry: unclassified HTTP 400 errors trigger a single retry that collapses history through `strip_to_text_only()`, which normalizes all message content to plain text. Works across GLM-5 on Bedrock, local, and future providers without per-provider string matching, and sits last in the retry chain.
  - `strip_to_text_only` evolved to convert tool parts (`ToolCallPart`, `BaseToolReturnPart`) and `ThinkingPart` into descriptive `TextPart` content, truncating large tool results to 500 chars and labeling unnamed tool calls.
  - Removed the `current_message is not None` guard so the text-only fallback also fires during tool-call iterations and outer-retry resume, injecting a `[SYSTEM]` fallback prompt when no message is pending.
  - Fixed `is_invalid_tool_call_error` false-positives by reading the provider message from `e.body` instead of `str(e)`.
  - Fixed `create_agent` to pass `tool_retries` (pydantic-ai renamed it from `retries`); tool-retry config was previously silently ignored.

- **Performance: Faster UI and snapshots**:
  - New `_schedule_invalidate()` coalesces rapid output appends into a single invalidation per ~16ms frame (33–100x fewer `invalidate_ui()` calls), with a synchronous fallback when run outside an async context.
  - `SnapshotManager` now skips large regenerable directories via a `DEFAULT_IGNORE_DIRS` frozenset (`.venv`, `node_modules`, caches, etc.), cutting backup/restore from multi-second to sub-second on large projects.
  - Adaptive UI refresh loop: idle 3.0s, thinking/confirmation fast-poll at 0.25s.

- **UI: Status bar and assistant naming**:
  - Animated thinking indicator (`Zrb is working.` → `..` → `...`).
  - Status bar styling moved to inline `CFG.LLM_UI_STYLE_*` strings using pure ANSI codes (compatible with all terminals including tmux); bottom toolbar set to `noinherit`.
  - Assistant name now auto-capitalizes its first letter (`"zrb"` → `"Zrb"`) across UI, prompt, and persona, preserving remaining casing; `StdUI` accepts a configurable `assistant_name`.

- **Resource safety: Stream cleanup**:
  - Stream consumption switched to `async with agent.run_stream_events(...)` to guarantee cleanup and fix a leak during cancellation.

- **Prompt & mandate refinements**:
  - Added a rule-priority hierarchy (`AGENTS.md`/`CLAUDE.md` win on style/conventions; base rules win on safety), split new-code-vs-existing-code guidance, cross-referenced git rules, consolidated testing rules, and removed redundant sections.
  - Clarified tool docstrings and deduplicated tool guidance; relaxed the git diff-sharing threshold.

- **Security**:
  - Pinned `urllib3 >=2.7.0` (CVE-2026-44432, HTTPS→HTTP redirect cookie leakage).
  - Removed the quarantined `mistralai` optional dependency and purged it from the lockfile (no source imports, no breaking change).

- **Config & docs**:
  - `ZRB_LLM_PLUGIN_DIRS` now expands `~` via `os.path.expanduser()`.
  - `OutputMixin` exposes `is_thinking`/`current_confirmation` as public properties.
  - Docs updated: version references bumped to 2.26.8, and task examples migrated to `BaseTask`/`_exec_action()` with retry-behavior guidance and a warning against overriding `run()`.

## 2.26.0 (May 10, 2026)

- **Feature: Multimodal Attachment Pipeline**:
  - New `LLM_MULTIMODAL_MODEL` env var / `LLMConfig.multimodal_model` property for designating a vision-capable model used to describe attachments when the main model is text-only.
  - New `LLM_MAX_IMAGE_DIMENSION` (default `1568`, Anthropic no-extra-cost tier) and `LLM_IMAGE_JPEG_QUALITY` (default `85`) knobs control image scaling.
  - Pasted (`Alt+V` / `Ctrl+V`) and `/attach`-ed images are auto-scaled to the cap on the longest edge before being added to the prompt; opaque images re-encode to JPEG, alpha-bearing images stay PNG.
  - Before each agent run, `runner._apply_multimodal_fallback` walks the prompt content: if the main model can't consume an image/audio attachment, the multimodal model describes it and the description text replaces the binary; if no multimodal model is configured, the attachment is dropped with a `⚠️ Dropped <modality> attachment` warning rather than silently sent to a provider that will reject or ignore it.
  - New utilities at `src/zrb/llm/util/`: `image_scale.py` (Pillow-backed downscale), `modality.py` (per-provider name-pattern detection of image/audio/video support), `multimodal_describe.py` (one-shot describe sub-agent + substitution helper).
  - Audio attachments via `/attach` get the same describe/transcribe fallback. Video attachments are kept as-is for Gemini-class models, dropped with a warning otherwise (auto frame-extraction is out of scope).

- **Performance: Defer default UI import in `zrb.llm.ui`**:
  - Moved `from zrb.llm.ui.default.ui import UI as _UI` from module top into the existing `__getattr__` so `prompt_toolkit` no longer loads on every `import zrb`.
  - Cuts ~25ms (~20%) off cold-import on a dev box; larger on slower machines (~250ms on a phone via Termux).
  - No public API change — `from zrb.llm.ui import UI` still works; the resolution is just lazy.

- **Dependency: bump `pydantic-ai-slim` to `~1.93.0`** (was `~1.90.0`).

- **Security: Bump `langchain-core` for CVE-2026-44843 (GHSA-pjwx-r37v-7724)**:
  - Pin raised from `>=1.2.28` to `>=1.3.3` (still in the `voyageai` extra).
  - LangChain's deserialization path used overly broad object allowlists, allowing prompt injection / credential disclosure via attacker-controlled structured input. CVSS 8.2.

- **Security: Correct `python-multipart` advisory description (GHSA-pp6c-gr5w-3c5g)**:
  - Pin unchanged at `>=0.0.27`. Comment updated — the actual issue is unbounded multipart **header count and size** causing CPU exhaustion, not the previously-described preamble/epilogue handling.

- **Tests**: 100% coverage for `src/zrb/llm/util/clipboard.py` (was 17%) and full coverage for the three new multimodal modules.

## 2.25.3 (May 8, 2026)

_Cumulative summary of the 2.25.1–2.25.3 patch line._

- **Feature: Zero-Setup Internet Search**:
  - New Google News RSS backend (`llm/tool/search/google_rss.py`) implements `SearchInternet` via the Google News RSS feed — free, no API key, no Docker. It is now the default (`DEFAULT_SEARCH_INTERNET_METHOD` changed from `serpapi`/`searxng` to `google_rss`); SearXNG is only used when `ZRB_SEARCH_INTERNET_METHOD=searxng` is explicitly set.
  - Fixed the SearXNG Docker setup: config copied to the correct `~/.config/searxng/settings.yml` path, corrected volume mount, pinned image (`2026.5.6-36bcd6b55`) to fix a Wikidata `KeyError`, per-run secret key via `secrets.token_hex(32)`, added `limiter.toml`, and a canonical `settings.yml` (added `json` format, removed Tor-only `ahmia`/`torch` engines).

- **Bug Fix: Agent Run Robustness**:
  - `filter_nil_content` no longer crashes on dataclass parts without a `content` field (e.g. `BuiltinToolCallPart` from provider-side tools like Anthropic web_search) — the replace is now gated on `hasattr(part, "content")`, and nil placeholder handling uses `BaseToolReturnPart` so builtin returns get `"null"`. This was hit on every model call with builtin tools enabled.
  - GLM-5 / Bedrock `ValidationException` responses with an empty `Error.Message` are now detected as missing-reasoning-content errors, triggering the existing `strip_thinking_parts` retry instead of surfacing as opaque 400s.
  - Removed a self-import in `attachment.py` and fixed a `default_llm_limitter` → `default_llm_limiter` typo throughout `llm_task.py`.

- **Performance: Session-Lifetime Caching**:
  - System context detection (project type, infrastructure, marker scanning, `which()` tool availability) is now `@lru_cache`d per-CWD, with the ThreadPoolExecutor reduced from 16 to 4 workers (only git status/log and todos stay dynamic); `is_inside_git_dir()` caches its `git rev-parse` check.
  - Prompt loading (`_find_custom_prompt`, search paths, package prompt reads) is `@lru_cache`d, and prompt replacements are keyed by journal index mtime so they only rebuild when the journal changes.
  - `LLMTask.get_system_prompt()` is now computed once and reused across `_create_agent()` and `run_agent()`, avoiding a second expensive rebuild per turn.

- **Improvement: Journaling Prompt Restructure**:
  - `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` now defaults to `off` independently of the `ZRB_LLM_INCLUDE_JOURNAL` master switch (which still guards it).
  - The journal mandate gained an autonomous-journaling directive and a "how to scan for journal-worthy content" guide, while the reminder was slimmed to a single lightweight `[SYSTEM REMINDER]` nudge.

- **Improvement: UI Confirmation Indicator**:
  - The status bar now shows a waiting-for-confirmation indicator (`👋 <name> is waiting for confirmation`) via the new `LLM_UI_STYLE_CONFIRMATION` style; `StdUI` shows an equivalent message on stderr, and the app invalidates unconditionally so the bar reflects transitions back to working/ready.

- **Refactoring: Structure, Typing, and Imports**:
  - The sub-agent manager moved to a nested `agent/subagent/manager/` package (matching `hook/manager/` and `lsp/manager/`), with `__init__.py` re-exporting the public names; `tool/delegate.py` imports the inner module directly to avoid a circular import.
  - All eight in-scope mixin pairs now declare host-class attributes via `if TYPE_CHECKING:` blocks for static interface checking with zero runtime attribute leaks.
  - A lazy-import sweep hoisted all 60 stdlib and 30 safe internal in-function imports to module top, keeping 13 genuinely-lazy imports tagged with `# lazy: <reason>`; the four lazy-import categories are now documented in a new `Imports` section of `AGENTS.md`.

- **Improvement: Lint Enforcement and Dead Code Removal**:
  - `flake8 src/zrb --select=F` now runs (gated before pytest) in `./zrb-test.sh`, catching unused imports and undefined names.
  - Removed unused utilities (`get_callable_name`, `truncate_str`) and eight stray unused imports.

- **Improvement: PyPI README Single-Source**:
  - `README.md` is now the single source of truth using relative `docs/X` links; a new `scripts/build_pypi_readme.py` rewrites them to absolute, version-tagged GitHub URLs into `README.pypi.md` (the packaged file), run by `publish-zrb-to-pip` so each release links to its matching version's docs.

- **Documentation**:
  - New `docs/advanced-topics/llm-chat-lifecycle.md` narrates `zrb llm chat "..."` end-to-end from CLI bootstrap to history persistence.
  - Reconciled the `ContextVar` count to seven across `architecture.md` and `maintainer-guide.md`, with a maintenance note added to `contextvars.py` to prevent drift.
  - Added short module docstrings to six high-traffic files.

## 2.25.0 (May 5, 2026)

- **Improvement: Comprehensive History Sanitization Layer**:
  - New `sanitize_history()` in `history_utils.py` is a 4-stage pipeline (filter nil content → strip orphaned tool calls → drop empty messages → ensure alternating roles) that replaces the single `filter_nil_content()` call in the execution loop.
  - New `_detect_problems()` logs invariant violations at DEBUG level before sanitization runs, enabling root-cause tracing of provider 400 errors.
  - New `sanitize_orphaned_tool_calls()` in `message.py` removes unmatched `ToolCallPart`/`ToolReturnPart` pairs that can appear after history compression.
  - New `strip_thinking_parts()` strips `ThinkingPart` from responses for providers (e.g., DeepSeek) that reject `reasoning_content` in multi-turn histories.
  - New `is_missing_reasoning_content_error()` in `error_classifier.py` detects DeepSeek V3.2/V4 errors where the provider requires `reasoning_content` in history — triggers a one-time retry with `strip_thinking_parts`.
  - `is_invalid_tool_call_error()` now requires BOTH an entity word ("tool"/"function") AND a problem word ("unknown"/"invalid"/etc.) to avoid false positives on generic HTTP 400 errors.
  - `filter_nil_content()` now catches empty strings (`if not part.content` instead of `if part.content is None`) and handles thinking-only responses by injecting a `TextPart(".")` placeholder.
  - `runner.py`: The execution loop now calls `sanitize_history()` instead of `filter_nil_content()`, with `allow_orphaned_tool_calls=True` when deferred tool results are pending.
  - `runner.py`: Removed unnecessary `await asyncio.sleep(0)` from the streaming event loop.
  - Documented in `docs/advanced-topics/maintainer-guide.md` under a new "LLM History Sanitization Layer" section.

- **Improvement: Prompt & Mandate Overhaul**:
  - `persona.md`: "State intent before tool calls" → "State what you're about to do, then call"; added "Skip pre-tool narration for single-tool calls" and "skip post-task summary when there's nothing to report."
  - `mandate.md`: Changed priority tiebreaker from `action > analysis` to `analysis > action`; removed "Git state changes" from confirm-before table (moved to git_mandate.md); renamed "Edge Cases" → "Engineering Discipline" with Scientific Method, Atomic Changes, No Magic, Defensive Not Paranoid, Review Your Own Code; replaced "No Hacks" with "Avoid band-aids" (acknowledging suppression annotations are sometimes necessary); added "Modularity" and "Comments" rules; added "Prefer idiomatic code over existing style," "Minimal Changes," "Understand First" to Scope & Simplicity; consolidated token efficiency rules into two bullets (Be concise, Prioritize recent context); expanded Execution Loop with Root Cause First, Tests Are Integral (TDD), Testing Standards (≥80%, AAA, no private members), Test File Conventions; renamed "Multi-Step Tasks" to its own section; removed the Edge Cases section entirely (lock files, merge conflicts, git hooks, etc.).
  - `git_mandate.md`: Restructured with "Requires Approval" now requiring `git status` + `git diff HEAD` before asking, with per-file summary for large diffs; "Always OK" → "No Approval Needed."
  - `journal_mandate.md`: Refined write criteria from "Write if reusable" to "Write if it would help future sessions"; "silently — never ask the user before journaling."

- **Bug Fix: Mutable Default Arguments**:
  - `cli.py`: `str_args: list[str] = []` → `list[str] | None = None` with `if str_args is None: str_args = []`.
  - `subcommand.py`: `paths: list[str] = []` and `nexts: list[str] = []` → `list[str] | None = None` with initialization guards.
  - `file.py`: `replace_map: dict[str, str] = {}` and `excluded_patterns: list[str] = []` → `list[str] | None = None` with initialization guards.

- **Maintenance: Dependency Update**:
  - Updated `pydantic-ai-slim` from `~1.88.0` to `~1.90.0`.
  - Updated `poetry.lock` to match.

- **Tests: Coverage Expansion**:
  - New `test/llm/config/test_limiter.py`: 144 lines for limiter configuration tests.
  - New `test/llm/util/test_stream_response.py`: 400 lines for stream response handling.
  - New `test/util/test_file_util.py`: 35 lines for file utility tests.
  - New `test/util/test_truncate.py`: 75 lines for truncation logic tests.
  - New `test/util/test_yaml.py`: 57 lines for YAML utility tests.

## 2.24.4 (May 3, 2026)

_Cumulative summary of the 2.24.1–2.24.4 patch line._

- **Bug Fix: History & Summarization Reliability**:
  - `drop_oldest_turn()` now honors a `min_turns` parameter and refuses to prune below it; `_execution_loop` passes `min_turns=1` when deferred tool results are pending, preventing history from being pruned to zero turns mid-tool-call and the resulting unrecoverable context-too-long failures.
  - The history summarizer now deducts the system prompt's token cost when comparing against `conversational_token_threshold`. `_prepare_history` counts system prompt tokens and passes them as a `system_prompt_overhead` argument; `create_summarizer_history_processor` computes an `adjusted_threshold`, replacing a prior side-channel attribute hack — so summarization triggers at the intended point.

- **Performance: Token Counting**:
  - `LLMLimiter.fit_context_window` pruning reduced from O(n²) to O(n) by precomputing per-message body token counts and a backward-scanned last-instruction index, then subtracting costs incrementally. Measured ~5× speedup at 40 turns up to ~46× at 320 turns.
  - `_prepare_history` now computes the token count once and reuses it when no history processors are registered, saving one O(n) traversal per chat turn.

- **Improvement: Prompt & Skill Verbosity Audit**:
  - Word-level audit across all prompt components, skills, and agent definitions cut ~25–30% overall while justifying every retained word.
  - Prompts tightened: `mandate.md` made idiom rules language-agnostic and quantified priorities (`correctness > speed, brevity > completeness, action > analysis`); `persona.md` simplified to a "Lead Engineer" identity; `journal_reminder.md` now scans only from the last journal write forward; `git_mandate.md` adds a per-file summary rule for diffs over ~100 lines; summarizer/extractor prompts gained `[BLOCKED]` status, marketing-claim handling, and broader file-type coverage.
  - Skills rewritten: dropped persona intros and added concrete triggers/thresholds across `core-coding`, `debug`, `testing`, `refactor`, `review`, `research-and-plan`, `core-journaling`, and `init` — including multi-language guidance, reference-check mandates, and quantified mock/large-diff thresholds.

- **Improvement: Agent Definitions & Tooling**:
  - Agent definitions (`generalist`, `code-reviewer`, `researcher`) lost persona fluff and gained `SearchJournal`, worktree tools, and the full LSP tool suite.
  - RM tool guidance in `chat.py` now reads "use Grep (or LspFindReferences)" for consistency with MV.

- **Improvement: `AGENTS.md` Accuracy**:
  - Removed the stale `llm/chat/` row, corrected ambient-state paths (`agent/run/runner.py`, `agent/run/runtime_state.py`), and named the `llm_plugin/` `skills/` and `agents/` subdirectories explicitly.

- **Maintenance**:
  - Updated `google-genai` from `>=1.66.0` to `>=1.70.0` (with `poetry.lock`) and removed unused `_images/fastapp/` assets.

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

_Cumulative summary of the 2.22.1–2.22.8 patch line._

- **Prompt System: Mandate, Persona & Guidance Refinements**:
  - `mandate.md` restructured across the line: added Pre-Task Clarity (later "Inquiries vs. Directives & Pre-Task Clarity"), Execution Loop ("Path to Finality" with Empirical Reproduction, Mandatory Verification, and a 3-strike Strategic Re-evaluation), Scope & Simplicity, Technical Integrity & Standards, and Context & Token Efficiency sections.
  - `persona.md` reframed identity as "Lead Engineer and Strategic Orchestrator" treating the context window as a precious resource; "Calibrate depth" → "Depth matches content"; added "Push back" rule and "One sentence before tools" calibration.
  - Reordered journal reminder for clearer journaling decisions.

- **System Context: Richer Runtime Awareness**:
  - Session identity now wired via a `ContextVar` (`set_current_session()`), so all four todo tools resolve session in async contexts; replaced the broken `threading.local` approach.
  - System prompt now injects active (pending/in_progress) todos, last 5 git commits, active worktree path, expanded infra detection (Terraform, Kubernetes, AWS, GCP, Azure), more utility tools (`jq`, `curl`, `gh`, `make`, `rg`, `rtk`), CLI preference hints, and the token limit.
  - `EnterWorktree`/`ExitWorktree` now track the active worktree via `ContextVar` and auto-add `.zrb/worktree/` to `.gitignore`.

- **Skills & Delegation**:
  - `ActivateSkill` now returns the skill directory path and companion file listing alongside content.
  - Tool guidance now propagates to sub-agents: a shared `_static_tool_guidance` list is broadcast to both the main agent and `SubAgentManager`, which gained `add_tool_guidance()`/`add_tool_group()`; `create_agent()` appends guidance to sub-agent system prompts.
  - Refined `DelegateToAgent`/`DelegateToAgentsParallel` guidance (parallel preferred for independent concurrent work; delegate heavy/repetitive work to keep main history lean).

- **Agent Resilience: Provider Error Handling & Retries**:
  - Transient provider errors (HTTP 429, 5xx) now retry with exponential backoff honoring `Retry-After`, capped by `LLM_API_MAX_WAIT` (default 60s) and `LLM_API_MAX_RETRIES` (default 3).
  - Invalid/unknown tool-name errors (HTTP 400, e.g. Ollama) trigger a one-time corrective `[SYSTEM]` message and retry.
  - Nil tool-call responses (e.g. DeepSeek via Cloudflare) now insert an empty `TextPart("")` before tool calls to satisfy API contracts.
  - Normalized all system messages to a consistent `[SYSTEM]` prefix; passed `request_limit=None` to lift pydantic-ai's 50-request tool-loop cap.

- **Tools: File Search, Editing & Bash**:
  - `search_files` now tries `rg --files-with-matches` first, falling back to Python `os.walk` and handling missing/erroring ripgrep gracefully.
  - `replace_in_file` gained whitespace-tolerant and indentation-flexible fuzzy matching, reporting normalization and fixing replacement-count reporting.
  - Bash default timeout raised 30s → 120s; added actionable `[SYSTEM SUGGESTION]` hints for common failures (port in use, command/module not found, connection refused); added a rule against querying state already in System Context.

- **Web Frontend**:
  - Adopted Jinja2 templating with a centralized `get_jinja_env()`, bundled a local `mermaid.min.js` (removing the external CDN dependency), and improved theme switching, layout, and chat-interface styling.
  - Server shutdown timeout made configurable via `CFG.WEB_SHUTDOWN_TIMEOUT` (in milliseconds).

- **Configuration**:
  - New `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` and `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` env vars give independent control over journal sections, both defaulting to `ZRB_LLM_INCLUDE_JOURNAL` (backwards compatible).

- **Refactoring: Extract-Mixin Across Core Classes**:
  - `Config` reduced from ~2435 to 59 lines, split into 12 focused mixins under `src/zrb/config/_mixins/`; public flat access unchanged.
  - `HookManager`, `LLMChatTask`, and `BaseUI` similarly split into focused mixins.
  - New `src/zrb/contextvars.py` centralizes the `ContextVar` index, with `runtime_state.py` (agent-run state) and `ambient_state.py` (tool-scoped state).
  - Broadened public API surface on `LLMChatTask`, `DefaultUI` mixins, `ChatSessionManager`, and `HttpUI`, replacing private-attribute access.

- **Security & Dependencies**:
  - Bumped `pydantic-ai-slim` (→ `~1.86.1`, with `AbstractCapability`/`capabilities` support), `anthropic` (→ `>=0.96.0`), and `boto3` (→ `>=1.42.63`).
  - Added security pins for transitive deps: `python-multipart >=0.0.26` (CVE-2026-40347 DoS), `langchain-text-splitters >=1.1.2` (SSRF), `langsmith >=0.7.31` (output-redaction bypass).

- **Bug Fixes**:
  - `SubAgentManager` now only treats `.md` files directly inside an `agents/` directory as agent definitions.
  - Fixed `os.make_dirs` → `os.makedirs` typo in `archive_todo` that caused `FileNotFoundError`.
  - RAG `_load_hash_file()` now catches and logs errors instead of crashing on a corrupt hash file.
  - YOLO inheritance check now reads `ui.yolo` directly; fixed mutable default arguments in `get_group_subcommands()`.

- **Challenge Runner**:
  - `VERIFICATION_RESULT` markers now take priority over exit codes, handling models that finish work but exit non-zero due to unrelated framework exceptions.

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

_Cumulative summary of the 2.20.1–2.20.2 patch line._

- **Security: Dependency Vulnerability Patches**:
  - Updated `Pillow` from `>=10.0.0` to `>=12.2.0` (CVE-2026-40192: decompression bomb via unlimited GZIP read in FITS decoding).
  - Updated `pytest` from `^8.3.5` to `>=9.0.3` (CVE-2025-71176: local privilege escalation via `/tmp/pytest-of-{user}` directories).

- **Feature: Bidirectional Journal Graph**:
  - Journal restructured as a bidirectional graph with a backlinks protocol.
  - Every forward link must have a backlink entry in the target note's `## Backlinks` section.
  - New Link Convention with relative paths from the journal root.
  - Step-by-step guide for creating new notes with proper backlink maintenance.
  - Updated `journal_mandate.md` with embedded index context and retrieval guidance.
  - Updated `core-journaling` skill with backlink protocol, maintenance rules, and ~50-line file limit guidance.

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

- **Improvement: Active Skills Tracking in Summarizer**:
  - New `<active_skills>` section in the `conversational_summarizer.md` state snapshot XML.
  - Skills activated via `ActivateSkill` are now tracked and restored on context recovery.
  - Restored agent re-activates skills if the task still requires that domain expertise.

- **Improvement: Worktree Repo-Local Storage**:
  - Worktrees now placed inside the repo under `.{ROOT_GROUP_NAME}/worktree/` instead of the system temp directory.
  - Uses `git rev-parse --show-toplevel` to resolve the git repo root.
  - Keeps worktrees co-located with the repository they belong to.

- **Improvement: Mandate Updates**:
  - Added "Memory Operations" as rule priority #4: journaling and skill activation are autonomous; exempt from Scope Discipline.
  - Marked Delegation and Skills sections with `*(if available)*` conditional markers.
  - Added `WriteMany`, `ClearTodos`, `ExitWorktree`, `ListWorktrees` to tool selection table.
  - Marked conditional tools with `*(if available)*` in the tool selection table.

- **Improvement: Tool Docstring Updates**:
  - `WriteTodos`: Replaced "Create todos before starting complex multi-step tasks" mandate with "Call `GetTodos` before each subtask to check current state".
  - `OpenWebPage`: Reformatted `MANDATE` to `MANDATES` with bulleted guidance.

- **Bug Fix: Session and Context Stability**:
  - `SharedContext.__init__` changed mutable defaults (`={}`, `=[]`) to `None` with proper initialization, preventing shared state between instances.
  - Replaced recursive `Session.get_root_tasks()` with iterative traversal using a visited set to prevent infinite loops with cyclic task graphs.
  - Wrapped `dict.values()` and `list` iterations with `list()` in `Session.terminate()` to prevent "dictionary changed size during iteration" errors.

- **Bug Fix: State Logger CPU Consumption**:
  - Changed state logger sleep from `asyncio.sleep(0)` to `asyncio.sleep(0.1)`, capping writes at ~10 per second instead of spinning at full CPU.

- **Bug Fix: Builtin Plugin Path Resolution**:
  - Fixed `Path(os.path.dirname(__file__)).parent` to `Path(__file__).parent.parent.parent` for correct builtin path in `SkillManager`, `HookManager`, and `SubAgentManager`.

- **Refactoring: Modernize Type Annotations**:
  - Replaced `Optional[X]` → `X | None`, `Union[X, Y]` → `X | Y`, `Dict` → `dict`, `List` → `list`, `Tuple` → `tuple` across LSP, agent, prompt, and tool modules.

- **Refactoring: Path Handling Migration**:
  - Replaced `os.path.dirname(__file__)` + `os.path.join` with `Path(__file__).parent` / path operations across all web route modules and prompt loading.

- **Refactoring: Deduplicate Repeated Logic**:
  - Extracted `_add_agents_from_root()` in `SubAgentManager` to eliminate repeated directory scanning across user home, project, and base search sections.
  - Extracted `_execute_task_group()` and `_skip_task_group()` helpers in `execution.py` to reduce duplication in successor/fallback execute and skip logic.
  - Extracted `_append_unique_tasks()` in `BaseTask` to consolidate `append_fallback`, `append_successor`, `append_readiness_check`, and `append_upstream`.
  - Extracted `_truncate_file_list()` helper in `file.py` to share truncation logic between `list_files()` and `glob_files()`.

- **Documentation: New and Expanded Docs**:
  - New `docs/advanced-topics/mcp-support.md`: MCP server configuration and discovery guide.
  - Expanded `docs/advanced-topics/llm-integration.md`: Added "Built-in LLM Tools" reference section covering all built-in tool categories.
  - Expanded `docs/advanced-topics/maintainer-guide.md`: Added "Context Propagation Internals" section documenting `ContextVar` usage patterns.
  - Expanded `docs/advanced-topics/upgrading-guide.md`: Added "Upgrading from 1.x.x to 2.x.x" section with migration table.
  - Expanded `docs/core-concepts/session-and-context.md`: Added "Ambient Context" section documenting `get_current_ctx()` and `zrb_print()`.

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

## 2.14.2 (March 29, 2026)

_Cumulative summary of the 2.14.1–2.14.2 patch line._

- **Enhancement: Improved LLM Prompt Guidelines**:
  - Restructured journaling triggers in `journal_mandate.md` with clearer examples and conditions.
  - Required mandatory `core-journaling` skill activation before writing journal entries.
  - Added a "Software Engineering" section to `mandate.md` requiring `core-coding` skill activation for coding tasks.
  - Simplified response style guidance in `persona.md` for better clarity.
- **Bug Fix: Type Annotation Correction**:
  - Fixed `dict[str, any]` to `dict[str, Any]` in `chat_tool_policy.py`.
  - Added the missing `from typing import Any` import.
- **Code Cleanup**:
  - Removed an unused `import sys` from `terminal_approval_channel.py`.
- **Security: Dependency Updates**:
  - Pinned `cryptography = "^46.0.6"` to address CVE-2026-34073 (transitive dependency via PyJWT).
  - Updated the `langchain-core >= 1.2.22` constraint for CVE-2026-34070.

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

_Cumulative summary of the 2.10.1–2.10.4 patch line._

- **Feature: Conversation History & Session Management**:
  - Added `history_formatter.py` to render pydantic-ai conversation history as human-readable text; `/load` now displays loaded history in the streaming style (💬/🤖 icons with timestamps, inline 🧰/🔠 tool calls/returns).
  - `FileHistoryManager.save()` now writes timestamped backup files (`<session-name>-YYYY-MM-DD-HH-MM-SS.json`) alongside the main session, normalizing names that already carry timestamps.
  - `/save` autocomplete now lists existing session names (for overwrite) plus a timestamp-based new-session name.

- **Feature: Subagent Status Streaming**:
  - Added `stream_to_parent` to `UIProtocol` and implemented it across `UI`, `StdUI`, and `BufferedUI` to bypass the BufferedUI buffer during subagent execution.
  - Subagent tool calls and results now display immediately in the parent UI via a `status_event` parameter in `stream_response.py`, instead of waiting for task completion.

- **Fix: Cancellation & Event Loop Robustness**:
  - Ctrl+C now cancels `_running_llm_task` before exiting, so a single press cancels running tasks and eliminates "Task was destroyed but it is pending!" errors.
  - Added double-await cleanup in `_process_messages_loop`, re-raised `CancelledError` in `_stream_ai_response`/`_run_shell_command`, and explicit `stream.aclose()` in `run_agent.py` for proper cancellation propagation.
  - All `asyncio.sleep()` calls in the scroll/process/trigger loops now catch `RuntimeError` and break cleanly, preventing "Event loop is closed" errors on shutdown.

- **Fix: Tool Display & Permissions**:
  - Deduplicated duplicate tool-call notifications in the deferred-tool flow (pydantic-ai fires `FunctionToolCallEvent` twice per `tool_call_id`) via `printed_tool_call_ids` tracking.
  - `chat_tool_policy.py` now inspects the `files` parameter for `WriteMany` calls so journal-directory writes are correctly auto-approved.

- **Refactor: Streamlined Prompt System**:
  - Converted `mandate.md` and `journal_mandate.md` to concise table-based formats, added an ordered "Decision Flow" section to the mandate, and introduced tier-aligned journal scope (Tier 1 skips journaling, Tier 2 journals only on discoveries).
  - Condensed project-context rules in `claude.py` (25 → 10 lines) and unified delegate-tool docs (`subagent` terminology, USAGE bullets referencing the mandate).
  - Corrected persona delegation wording to "Delegate when context isolation is beneficial."

- **Refactor: Lazy Initialization & Agent Naming**:
  - Removed `SkillManager`'s `auto_load` parameter in favor of a lazy `_ensure_scanned()` on first access, reducing startup overhead.
  - Renamed the `subagent` agent to `generalist` (file `subagent.agent.md` → `generalist.agent.md`).

- **Security: CVE-2026-23491 (pyasn1 DoS)**:
  - Pinned `pyasn1 >= 0.6.3` (transitive via `google-auth`) to fix an uncontrolled-recursion vulnerability where crafted ASN.1 payloads could cause DoS via recursion crash or OOM.

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

_Cumulative summary of the 2.9.1–2.9.2 patch line._

- **Refactor: LLM System Prompt Architecture**:
  - Restructured prompt files to be Mutually Exclusive, Collectively Exhaustive (MECE) with zero conflicts and no ambiguity.
  - Simplified the skill protocol in `mandate.md`, removed redundant conditions, and clarified the activation pattern.
  - Confirmed `git_mandate.md` already followed the correct Prohibitions/Protocol/Violation structure.

- **Fix: Strengthen LLM System Prompt Mandates**:
  - Restructured `journal_mandate.md` to the Protocol/Prohibitions/Hierarchy format (consistent with `git_mandate.md`) and clarified the hierarchy scope.
  - Added an explicit "When to Write (Examples)" section to `journal_mandate.md` with concrete triggers (user preferences, decisions, errors, session insights) and a clear "Do NOT write for trivial queries" prohibition, fixing a regression from 2.7.x where the condensed version lost actionable examples.
  - Added an explicit list of state-changing commands requiring approval and more read-only commands to `git_mandate.md`, and changed the protocol from `git add <files>` to the generic `git <command> <args>` pattern.

- **Documentation**:
  - Moved older changelog entries (2.8.x) to `docs/changelog-v2.md`.

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

_Cumulative summary of the 2.8.1–2.8.4 patch line._

- **Fix: LLM History Model Compatibility**:
  - Added `_filter_empty_responses()` to `FileHistoryManager` to strip responses with empty or `None` parts during history loading and saving, preventing "invalid message content type: <nil>" errors with models like GLM-5 via Ollama.

- **Fix: Windows Cross-Platform Robustness**:
  - Added `src/zrb/util/cli/terminal.py` with `get_terminal_size()` for reliable terminal size detection across platforms, with Windows `CONOUT$` support in `get_original_stdout()` and a fallback around `output.get_size()` to prevent UI crashes when console dimensions cannot be detected.
  - Detection tries `sys.__stdout__`, `sys.__stderr__`, `sys.__stdin__`, Windows `CONOUT$`, then `shutil.get_terminal_size()` with env var support.
  - Added explicit `encoding="utf-8"` to journal index reading (`prompt.py`) and shell history reading (`completion.py`) to avoid `UnicodeDecodeError` on Windows (default `cp1252`).

- **Configuration: ASCII Art Directory Rename**:
  - Renamed default `ASCII_ART_DIR` from `.zrb/llm/prompt` to `.zrb/ascii-art` to avoid confusion with `LLM_PROMPT_DIR`, updating `src/zrb/config/config.py` and docs accordingly.

- **Documentation: Overhaul and Default-Value Corrections**:
  - Added navigable Tables of Contents, quick-reference tables, breadcrumb navigation, callout boxes (Tip/Warning), clearer hierarchies, and table-based config/API references across all 19 documentation files.
  - Corrected environment variable defaults: `ZRB_WARN_UNRECOMMENDED_COMMAND` (`"on"`), `ZRB_USE_TIKTOKEN` (`"off"`), `ZRB_LLM_MODEL` (`"openai:gpt-4o"` when unset), `ZRB_LLM_SMALL_MODEL` (falls back to main model), and clarified `ZRB_LLM_ASSISTANT_ASCII_ART` refers to the art name, not its content.

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
_Cumulative summary of the 2.7.1–2.7.2 patch line._

- **Performance: Battery Drain Reduction & UI Optimization**:
  - Reduced CPU usage by decreasing UI refresh frequency from 0.05s to 0.5s (`refresh_interval=0.5`) in `src/zrb/llm/app/ui.py`, cutting continuous CPU consumption during idle periods.
  - Changed system information (CWD and Git status) update frequency from every 2 seconds to every 60 seconds, eliminating unnecessary background polling.
  - Reduced output scrolling check frequency from 0.1s to 5.0s, minimizing UI thread activity.
  - Refactored update logic by extracting system info updates into a dedicated `_update_system_info()` method, with an initial update on UI startup for better responsiveness.

- **Reliability: Tool Call & MCP Server Retry Mechanisms**:
  - Added `max_retries=3` to `FunctionToolset` initialization in `src/zrb/llm/agent/common.py` to handle transient tool execution failures gracefully.
  - Enhanced MCP server creation in `src/zrb/llm/tool/mcp.py` with `max_retries=3` for both `MCPServerStdio` (stdio-based) and `MCPServerSSE` (SSE-based) servers.
  - Added `await self._update_system_info()` calls after LLM task completion to ensure the UI reflects current system state.

- **Compatibility: Cross-Platform UTF-8 Encoding**:
  - Added `encoding="utf-8"` to file operations across the codebase for consistent behavior across operating systems, particularly Windows where the default encoding is cp1252.
  - Updated `src/zrb/util/file.py` (core file writing), `src/zrb/llm/tool/rag.py` (RAG hash file read and write), `src/zrb/llm/tool/bash.py` (background PID collection), `src/zrb/llm/hook/manager.py` (hook configuration loading), `src/zrb/llm/tool_call/response_handler/default.py` (content editor response handler), `src/zrb/llm/tool_call/response_handler/replace_in_file_response_handler.py` (replace-in-file response handler), and `llm-challenges/runner.py` (log file writing).

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

_Cumulative summary of the 2.6.1–2.6.24 patch line._

- **Features: New Configuration & Integration Surface**:
  - Added 8 `LLM_INCLUDE_*` config properties (persona, mandate, git_mandate, system_context, journal, claude_skills, cli_skills, project_context) controlling PromptManager components, all settable via `ZRB_LLM_INCLUDE_*` env vars with `None` falling back to defaults; later exposed matching property getters/setters for dynamic configuration.
  - Introduced a four-level prompt override hierarchy (`ZRB_LLM_PROMPT_DIR` > direct env override > new org-wide `ZRB_LLM_BASE_PROMPT_DIR` > package default).
  - Made `FileSessionStateLogger.session_log_dir` accept a callable for dynamic runtime resolution while preserving string support.
  - Added Ollama model auto-completion to the UI, fetching local models via `ollama ls` (30s cached) formatted as `ollama:<model-name>`.
  - Added a git-aware system context: new `is_inside_git_dir()` utility so the git mandate is only included inside git repositories.

- **LLM: Message Safety & History Summarization**:
  - Centralized LLM message logic in `src/zrb/llm/message.py`, enforcing strict role alternation (merging consecutive same-role messages immutably) and tool call/return pair integrity across history processing and summarization.
  - Overhauled the history summarizer with a four-phase splitting strategy and scoring-based best-effort splits, with robust handling of orphaned returns and incomplete tool pairs.
  - Added deep-copy protection for mutable tool results and a centralized `to_string()` utility for safe (JSON-aware) conversion of tool return content, replacing brittle string-prefix detection with type-based detection (`ToolDenied`/`ToolApproved`); standardized `SUMMARY_PREFIX`/`TRUNCATED_PREFIX` constants.
  - Proactively cleaned corrupted (boolean/number/dict/list/None) content in `FileHistoryManager` on both load and save to prevent pydantic-ai serialization issues.
  - Fixed PRE_COMPACT hook to fire before summarization with richer context (token_count, message_count, has_history_processors).

- **LLM: Tooling, Truncation & Prompt System**:
  - Centralized output truncation in `src/zrb/util/truncate.py` (`truncate_output`), adopted by Bash, Read/file, and Grep tools; added a multi-stage character-limit algorithm with head/tail/middle preservation and accurate `TruncationInfo` metadata, and enforced a 1,000-char per-line cap to prevent minified/single-line files from bloating history.
  - Added `auto_truncate` and `exclude_patterns` parameters across file tools (`list_files`, `glob_files`, `search_files`, `read_files`, `analyze_code`) for flexible exclusion control over `DEFAULT_EXCLUDED_PATTERNS`.
  - Standardized tool docstrings to a concise usage-focused MANDATES format across bash, file, code, web, and related tools, including non-interactive-flag and timeout guidance.
  - Refactored core prompts (persona, mandate, git_mandate, journal_mandate) for token efficiency (~7K to ~5.8K tokens) while strengthening directives; restructured AGENTS.md as a practical guide.
  - Improved token estimation accuracy (char/3 to char/4 fallback) and dictionary token counting.
  - Strengthened the git mandate with assertive ABSOLUTE RULES, visual alerts, and per-operation separate-approval requirements; added a task-cancellation protocol mandating immediate cessation of tool calls.

- **LLM: Skills & Agents**:
  - Consolidated and renamed skills (e.g. `core_journal`→`core-journaling`, `test`→`quality-assurance`, `research`→`research-and-plan`), migrated all skill names to kebab-case, and removed redundant skills; folded the multiple specialized sub-agents into a single general `subagent.agent.md`.
  - Enhanced `ActivateSkill` with a RELOAD REQUIRED directive so summarized conversations can re-load skill instructions.

- **Fixes: Compatibility & Interaction**:
  - Fixed pydantic-ai toolset integration by aligning `SafeToolsetWrapper.call_tool()` with the `WrapperToolset` base signature (pydantic-ai 1.60.0), restoring MCP toolset loading; consistently wrapped tool/toolset results and errors in `ToolReturn` objects.
  - Fixed `analyze_file` API breakage by adding `auto_truncate=True`, and fixed a missing `_remove_lines_from_middle()` helper in the truncation algorithm.
  - Fixed non-interactive edit confirmation by using `ToolCallHandler` (policies, formatters, response handlers, including the 'e' edit option).
  - Made interactive input thread-safe via `prompt_toolkit` async prompting, handling Ctrl+C and EOF gracefully instead of hanging.
  - Buffered captured stdout/stderr until the UI closes and cleared the buffer after tool confirmation to prevent output leakage; preserved full user rejection reasons (removed the 500-char truncation cap).
  - Made hook execution sequential with proper error propagation and blocking behavior.

- **Web UI / Infrastructure**:
  - Standardized web auth env vars (`ZRB_WEB_SECRET`→`ZRB_WEB_SECRET_KEY`, plus `ZRB_WEB_AUTH_*_TOKEN_EXPIRE_MINUTES`) with backward-compatible mapping.
  - Refactored SearxNG configuration to auto-copy settings into `~/.config/searxng/` via a `copy_searxng_setting` task wired as an upstream dependency of `start-searxng`.

- **Maintenance**:
  - Updated core dependencies (pydantic-ai-slim, anthropic, cohere, huggingface-hub, voyageai) and expanded test coverage across the LLM, hook, summarizer, and tool subsystems.

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

_Cumulative summary of the 2.5.1–2.5.3 patch line._

- **Feature: SubAgentManager API Consistency**:
  - Added `append_tool()` and `append_tool_factory()` to `SubAgentManager` to match the `LLMTask` pattern.
  - Added toolset management (`append_toolset()`, `append_toolset_factory()`, `_get_all_toolsets()`) for better toolset integration.
  - Refactored existing `add_tool()`/`add_tool_factory()` to delegate to their `append_*` counterparts, preserving backward compatibility.
  - Exported `create_delegate_to_agent_tool` from `src/zrb/llm/tool/__init__.py`.

- **Fix: Circular Dependency in LLM Tool Imports**:
  - Reorganized LLM tool imports in `src/zrb/llm/agent/manager.py` from a flat structure into specialized modules (`zrb.llm.tool.code`, `.file`, `.bash`, `.web`) to break import cycles while maintaining full functionality.

- **Refactor: Journal Prompt System Migration to Markdown Templates**:
  - Replaced the dynamic `create_journal_prompt()` function with a static `journal.md` template, aligning with the existing prompt pattern (persona.md, mandate.md).
  - Updated `PromptManager` to use `get_journal_prompt()` instead of the middleware factory.
  - Added auto-approve policies for Write, WriteMany, and Edit tools when operating within the journal directory.

- **Improvement: Persona Refinement**:
  - Fixed "Orchstrator" → "Orchestrator" typo in the agent persona.
  - Updated the "Polymath Executor" persona with stronger emphasis on hands-on, brownfield development and reduced strategic delegation bias.

- **Maintenance**:
  - Version bumped to 2.5.3 in `pyproject.toml`.
  - Updated poetry.lock with Poetry 2.3.1 and minor dependency specifier changes.

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
_Cumulative summary of the 2.4.1–2.4.2 patch line._

- **Feature: Robust LLM Summarization & History Management**:
  - Implemented dual-threshold summarization logic with separate thresholds for individual large messages and total conversational history to prevent context window overflows during long sessions.
  - Added `_ensure_alternating_roles` to the history processor, enforcing the User -> Assistant pattern required by LLM providers.
  - Added a recursion depth guard (max 5) and progress verification to `summarize_long_text` to prevent infinite summarization loops.
  - Enhanced history splitting so tool call/result pairs are never orphaned, maintaining the integrity of Pydantic AI message sequences.

- **Improvement: LLM Limiter Token Counting Optimization**:
  - Refactored `LLMLimiter._to_str` to use direct string concatenation for lists and dictionaries, avoiding JSON serialization overhead and resolving an O(N²) performance bottleneck that caused exponential latency as history grew.
  - Added a `skip_instructions` parameter to align with Pydantic AI's behavior of only counting current instructions, since historical instructions are not replayed to the model.
  - Reduced string length for nested structures from ~20k to <10k characters.
  - Enhanced handling of complex message structures with separate processing for parts, instructions, content, and args fields, keeping rate limiting precise even with large tool outputs.

- **Refinement: Summarizer Prompt & State Logic**:
  - Updated `summarizer.md` with a goal evolution system that detects when objectives are met and pivots the agent's focus, preventing conclusion loops.
  - Wrapped state snapshot components in CDATA sections to prevent XML parsing errors and ensured "Silent Thinking" for more reliable structured output.
  - Hardened the summarizer prompt against adversarial content and formatting distractions within the history.

- **Improvement: Agent Delegation & Operational Clarity**:
  - Updated the agent persona from "Polymath Agent" to "Lead Architect and Polymath Orchestrator" with stronger emphasis on strategic command and surgical delegation.
  - Clarified DEEP PATH delegation with an explicit "SURGICAL SCOPE" directive, requiring narrow, atomic tasks for sub-agents and prohibiting "explore and fix" patterns.
  - Enhanced delegation failure handling with better context management and redundant history purging during forced execution.

- **Documentation**:
  - Updated `AGENTS.md` (Section 6) with detailed technical documentation of the summarization system.

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
_Cumulative summary of the 2.3.1–2.3.5 patch line._

- **Prompt System: Assertive Operational Mandates**:
  - Rebuilt `persona.md` and `mandate.md` around strict **MUST ALWAYS** / **NEVER** directives, shifting from descriptive guidance to non-negotiable engineering mandates.
  - Mandated a strict tool discovery hierarchy (`Read` > `Glob` > `LS`) to eliminate redundant token use and prevent blind exploration of known paths.
  - Upgraded implementation into a mandatory **Plan -> Act -> Validate** cycle, forbidding assumed success without test/linter verification.
  - Clarified FAST PATH vs DEEP PATH delegation criteria with context saturation risk assessment, added a recovery protocol for failed delegation, and emphasized user visibility of sub-agent outputs.

- **Memory & Context Management**:
  - Introduced "high-signal" memory: save only small, rarely-changing architectural facts or user preferences via `WriteContextualNote` and `WriteLongTermNote`.
  - Mandated a read-before-write workflow to avoid context loss and duplication, and improved state snapshots to prioritize evidence-backed insights over raw history.

- **Feature: LLM Task Error Retry with History Preservation**:
  - `run_agent()` attaches conversation history (`zrb_history`) to exceptions and wraps its execution loop in try-except so retries keep full context.
  - `LLMTask` saves error details to history, includes a retry attempt count in subsequent prompts (`[System] This is retry attempt N`), maintains conversation continuity, and detects duplicate user messages.
  - Added `_handle_run_error()` for automatic error/tool-return recovery and an `attempt` property on `AnyContext` / `Context`.

- **Specialized Agent System**:
  - Redefined the coder agent as a "Senior Staff Engineer and Brownfield Expert" for safe, zero-regression legacy integration.
  - Added an Explorer agent (read-only codebase mapping) and a Generalist agent (polymath executor for complex multi-step tasks); enhanced planner, researcher, and reviewer agents.
  - Integrated the history summarization processor into agent creation, with proper SharedContext-based context initialization for sub-agents.

- **Tooling & Optimization**:
  - Enhanced `AnalyzeCode` with an `include_patterns` parameter and mandated `extensions`/glob patterns to limit search space; tightened `search_files` (Grep) and `analyze_file` docstrings.
  - Enforced an "OpenWebPage Mandate" requiring full content verification of search snippets and citation of verified sources.
  - Improved summarizer defaults (summary window handling, token threshold logic with config fallback).

- **Bug Fix: Token Counting Robustness**:
  - Refactored `LLMLimiter._to_str()` to handle complex Pydantic AI message structures: basic-type handling, safe `getattr()` defaults, and recursive dict traversal, fixing token-estimation inaccuracies for tool calls/returns and improving rate-limiting and context-window accuracy.

- **TUI & UX Refinement**:
  - Added F6 to toggle focus between input and output fields and removed redundant TAB hints.
  - Implemented smarter scrolling that keeps latest content in view, and raised the UI refresh rate to `0.1s` for smoother streaming with fewer artifacts.

- **LLM Challenge Framework & Evaluation**:
  - Added an "integration-bug" challenge (banking-system scenario) and refactored the feature challenge into a realistic FastAPI app structure; standardized verification scripts across challenge types.
  - Expanded benchmarking across 10+ LLM providers with updated `REPORT.md` metrics and standardized baseline experiment directories.

- **Refactoring & Test Coverage**:
  - Decomposed the monolithic `LLMTask._exec_action()` into focused helpers (history manager, summarization check, agent/event-handler creation, retry-aware prompt, error handling, output post-processing).
  - Added a retry test suite plus 20+ new test files spanning agent manager, run agent, history processors, hooks, prompts, tools, config, and utilities, with summarizer resilience/edge-case tests.

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

_Cumulative summary of the 2.2.1–2.2.15 patch line._

- **Feature: Hook System**:
  - Added a robust, Claude Code-compatible declarative hook system with 100% event parity, a thread-safe `HookExecutor` with configurable timeouts, and advanced field matchers (regex, glob, contains).
  - Supported `Command`, `Prompt`, and `Agent` hook types with automatic environment injection, plus new Hook System and Quick Start guides.

- **Feature: Extended LLM Provider Support**:
  - Added native xAI (Grok) support via the `xai` extra and `xai-sdk`, plus Voyage AI embeddings/RAG via the `voyageai` extra with automatic dependency management.
  - Added environment variable configuration for xAI and Voyage AI API keys and base URLs, and upgraded `pydantic-ai-slim` and `anthropic`.

- **Feature: Skill System**:
  - Added comprehensive skill definitions for common workflows (`commit`, `debug`, `init`, `plan`, `pr`, `research`, `review`, `skill-creator`, `test`), exposed as user-invocable slash commands with structured, step-by-step guidance.

- **Feature: Tool Call Validation Policies**:
  - Added validation policies that proactively reject invalid tool calls: `Read` on a missing file, `ReadMany` when no files are found, and `Edit` when `old_text`/`new_text` are identical, the file is missing, or `old_text` is not present.
  - Integrated these policies into the built-in `llm_chat` task to reduce failed tool executions and improve agent recovery.

- **Improvement: Summarization & History Processing**:
  - Introduced a two-tier summarization system: a conversational summarizer producing structured XML `<state_snapshot>` output (goals, constraints, knowledge, reasoning, artifacts, task states) and a message summarizer for large individual tool results.
  - Refactored the monolithic `summarizer.py` into a modular `src/zrb/llm/summarizer/` package, added an emergency failsafe with automatic pruning, smart merging of consecutive `ModelRequest` messages, intelligent chunking of huge outputs, and tool call/return pair integrity guarantees with best-effort splitting.
  - Raised the default history summarization window over the line (5 → 12 → 30 → 100 messages) and added granular conversational/message summarization token thresholds.

- **Improvement: Agent Prompts & Behavior**:
  - Redefined the persona as a "Polymath AI Assistant" adapting across coding, writing, and research contexts, with explicit code/prose style mimicry and a preference for maintainability and the "Standard Way."
  - Added mandatory `<thought>` reasoning before responses and tool calls, a structured DEEP PATH workflow (RESEARCH, STRATEGY, EXECUTION, FINALITY), empirical bug reproduction before fixing, and error-recovery backtracking.
  - Restructured the mandate and agent definitions (Coder as "Senior Software Engineer," Planner as "Systems Architect"), strengthened the sub-agent delegation protocol to require full context, and mandated proactive note-taking for knowledge stewardship.

- **Improvement: TUI / UX**:
  - Redesigned the main layout to remove redundant framing and maximize vertical space, added a dynamically-sized multi-line input (up to 10 lines), and refined Title/Info/Status bars to reduce flickering.
  - Improved navigation and keybindings (F6 focus toggle, Tab/Shift+Tab, smarter history navigation and printable-character redirection), enhanced output-field scrolling with cursor preservation, and added robust clipboard fallback when `pyperclip` is unavailable.
  - Added a message queue ensuring only one LLM task or shell command runs at a time, blocked new input while the LLM is processing, and improved tool-call visualization for file operations.

- **Refactor: Tool Standardization**:
  - Renamed all LLM tools to PascalCase Claude-standard aliases (`read_file` → `Read`, `write_file` → `Write`, `replace_in_file` → `Edit`), cleaned up the tool registry, and aligned tool policies and agent definitions accordingly.
  - Standardized tool-call component file naming (e.g. `*_formatter.py`, `*_response_handler.py`).

- **Bug Fixes**:
  - Fixed `ToolDenied` attribute access to use `message` instead of a non-existent `reason`.
  - Resolved a TUI broken-pipe regression from async hook calls in background threads and added explicit error reporting for external triggers.
  - Reworked thinking-tag removal into a stack-based parser (`util/string/thinking.py`) that correctly handles nested, unclosed, and mixed `<thinking>`/`<thought>` tags, stripping ANSI codes first.
  - Restored mandate.md content corrupted by placeholder text, and fixed ANSI-aware banner width/padding for correctly aligned ASCII art.

- **Security & Configuration**:
  - Added prompt-injection defenses to summarizer prompts, strict token-budget enforcement for state snapshots, and explicit `.env`/`.git` protections.
  - Standardized token config property names (e.g. `LLM_MAX_TOKENS_PER_MINUTE` → `LLM_MAX_TOKEN_PER_MINUTE`) with backward compatibility, raised the default per-minute token limit, and constrained `griffe` for Termux compatibility.

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

_Cumulative summary of the 2.0.1–2.0.19 patch line._

- **Feature: Skills as slash commands & active skills**:
  - Auto-converted user-invocable Claude skills into executable `/<skill-name>` slash commands in the chat TUI, with dynamic argument detection and parsing.
  - Distinguished model-invocable from user-invocable skills.
  - Added `active_skills` and `render_active_skills` parameters to `PromptManager`, `LLMTask`, and `LLMChatTask` to pre-load skill content into system prompts, dynamically resolved from context at compose time; tasks auto-instantiate a `PromptManager` when these are provided.
- **Feature: Skill discovery & management**:
  - Added `max_depth` recursive scan control and customizable `ignore_dirs` to `SkillManager`, with robust handling of permission errors and inaccessible directories.
  - Expanded discovery to look in `.zrb/skill` (configured root group) alongside `.claude/skills`; standardized the Zrb skill directory to `~/.zrb/skills`.
- **Feature: Runtime model & YOLO control**:
  - Added `/yolo` and `Ctrl+Y` to toggle tool-approval skipping at runtime, and `/model <name>` to switch models on the fly.
  - VS Code-style fuzzy autocompletion for commands and model names, including a generated list of supported models from pydantic-ai.
  - The built-in `llm_chat` task accepts a `model` input for dynamic selection.
- **Feature: Context-aware agent execution**:
  - Introduced `ContextVar`-based context management (`current_ctx`, `zrb_print()`) so sub-agents inherit parent UI and tool-confirmation settings, with consistent context-aware printing across the codebase and proper context set/reset during task runs.
  - Added `tool_factories`/`toolset_factories` to `LLMChatTask` for runtime tool resolution; used `Xcom` for shared state (YOLO mode) synchronization.
- **Feature: Structured history summarization**:
  - Overhauled the summarizer to emit a structured `<state_snapshot>` XML (Goals, Constraints, Knowledge, Artifacts, Tasks) instead of free text.
  - Added iterative chunking and recursive re-compression to handle large conversations without context-window overflow.
  - Added `message_to_text()` for readable history; LLM chat tasks now include a summarizer history processor by default.
  - Added prompt-injection defenses instructing the summarizer to ignore adversarial chat content.
- **Feature: Sub-agent delegation & plugin agents**:
  - Implemented a `delegate_to_agent` tool with smarter detection of when to hand off to specialized sub-agents.
  - Moved built-in agent definitions (Coder, Planner, Researcher, Reviewer) into a dedicated `src/zrb/llm_plugin/agents/` plugin structure, with `PromptManager` refactored to match.
- **Feature: LLM challenge suite**: Added benchmarking challenges under `llm-challenges/` (bug fixing, refactoring, copywriting) with runner scripts and experiment results refreshed to track improved agent behavior.
- **Improvement: Prompt management**:
  - Hierarchical prompt discovery now traverses up the directory tree (to home) for custom overrides.
  - Added markdown role prompts (executor, orchestrator, planner, researcher, reviewer) and let `PromptManager` accept raw strings, auto-wrapping them with context rendering.
  - Split skills prompt into `create_claude_skills_prompt` and `create_project_context_prompt`, with an `include_project_context` toggle.
  - Polished `mandate.md`/`persona.md`: more assertive mandate requiring system-context checks before discovery tools, stricter verification (keywords, structure, citations), anti-hallucination guidance, clearer concise-vs-detailed protocol, plus loop-prevention for Coder, planning rigor for Planner, and a mandated References section for Researcher.
- **Improvement: Rate limiting & token management**:
  - Rate limiter accepts message/history context for more accurate estimation; improved token counting (char/3 fallback, 95% buffer) and graceful empty-log throttling.
  - Added token-aware `truncate_text` to `LLMLimiter` (tiktoken with fallback) and clearer, styled rate-limit notifications.
- **Improvement: Tool safety & robustness**:
  - Centralized tool/toolset error-handling wrappers into `create_agent` so faulty tool calls report gracefully instead of crashing the agent.
  - Safer `auto_approve` policy with directory-aware checks (auto-approving reads only within the working directory).
- **Improvement: Config consistency**: Renamed `LLM_MAX_REQUESTS_PER_MINUTE` to singular `LLM_MAX_REQUEST_PER_MINUTE` (old env var still honored); more flexible defaults for web components and token thresholds.
- **Improvement: UI/UX**: Consistent faint/error styling, inline timestamps, streamlined command display, and summarization progress notifications.
- **Bug Fixes**:
  - Resolved "Unknown model" errors by preventing custom `Model` objects from being stringified when passed to sub-tasks; `LLMConfig` now resolves providers by model name so custom `base_url`/`api_key` apply to OpenAI-compatible models while native Anthropic/Google providers still work.
  - Treated empty-string model names as `None` to avoid resolution failures.
  - Sanitized `Session.as_state_log()` inputs to prevent `PydanticSerializationError` on non-serializable objects.
  - Added `if __name__ == "__main__":` to `__main__.py` for correct `python -m zrb` execution.
  - Ensured `FileHistoryManager` is initialized before use; fixed lazy load of `CFG.LLM_ASSISTANT_NAME`.
  - Fixed skill command factory signature and custom-command resolution; corrected `create_faint_printer()` and argument-extraction handling.
  - Excluded the `.claude` directory from code analysis and fixed ASCII art resolution for user-provided files.
- **Documentation**: Added the "Customizing the AI Assistant" guide, updated `AGENTS.md`, and refreshed task-type, configuration, and architecture docs for the 2.0 architecture.
- **Update: ASCII art**: Added new art (`batman`, `butterfly`, `clover`, `hello-kitty`, `star`) and updated the banner format.

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
