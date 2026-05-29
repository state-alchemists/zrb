🔖 [Documentation Home](../README.md)


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

- **Feature: Post-write/post-edit diagnostics**:
  - New `src/zrb/llm/tool/post_write_check.py`: `format_post_write_diagnostics()` runs `ast.parse` + `pyflakes` on Python files after Write/Edit tool calls, surfacing syntax errors and undefined names inline in the tool result. Non-Python files and error-free files produce no output.
  - `write_file()` (`file_write.py`) and `replace_in_file()` (`file_edit.py`) are now `async` and append a `[DIAGNOSTIC]` section to their return value when errors are detected — the model sees errors immediately and can fix them in the same turn.

- **Feature: LSP push-diagnostics plumbing**:
  - `LSPServer` (`lsp/server.py`) gained `did_open_text_document()` and `did_change_text_document()` with full `didOpen`/`didChange` state tracking per URI. `get_diagnostics()` now synchronizes the file with the server via `didOpen`/`didChange`, then polls for `textDocument/publishDiagnostics` push notifications (50ms interval, 1.5s timeout), falling back to LSP 3.17 pull-diagnostics. Incoming `publishDiagnostics` notifications are cached in `self._diagnostics`.
  - Test updated to assert against the push-notification path instead of the pull-diagnostics response.

- **Feature: Installer LSP server setup**:
  - `install.sh` and `install.ps1` both gained `install_lsps()`: installs `python-lsp-server[all]` unconditionally, then optionally installs `typescript-language-server` (JS/TS), `gopls` (Go), and `rust-analyzer` (Rust) when their toolchains are present. Users are prompted during installation.

- **Improvement: Prompt and tool guidance deduplication**:
  - `common_tools.py`: Redundant tool guidance entries removed — Read's `old_text` note, Write's overwrite warning, Edit's read-first rule, Grep's truncation note — these are already documented in the tool docstrings themselves.
  - `lsp/tools.py`: MANDATES sections removed from all 8 LSP tool docstrings. The usage rules remain in `tool_guidance.py` (the single source of truth).
  - `rag.py`: MANDATES removed from RAG tool docstring; replaced with a one-line usage instruction.
  - `tool_guidance.py`: Parallel-tool-call sections rewritten in plain language — no emoji, no ALL-CAPS, no concatenated-tool-name examples. Heading normalized to `## Tool Call Parallelism` for both supported and unsupported models.

- **Improvement: Mandate.md strengthened**:
  - Destructive action rule expanded: `package downgrades`, `CI/CD changes`, `posts to Slack/email/PRs` added. New clause: investigate unfamiliar state (unexpected files, branches, stashes, lock files) before destroying — `--no-verify`, `rm -rf`, `git reset --hard` are not shortcuts.
  - Scope rule promoted above Memory (priority 6 → 5). Added scope-scoping rules: approved edit to file X ≠ approval to refactor file Y; approval is one-shot per action.
  - Understand step: hypothesis threshold softened from "3+ tool calls" to "two distinct hypotheses failed".
  - Plan step: explicitly states it describes *what changes where*, not a preamble.
  - Execute step: broken into sub-bullets; `DelegateToAgent` gate removed (moved to tool guidance).

- **Improvement: Persona.md tightened**:
  - Removed "Your context window is a budget" line (covered by mandate completeness rule).
  - Source citation format expanded: `file:line-range` and `file:symbol` added alongside existing `file:line`.

- **Improvement: Tool docstring refinements**:
  - `file_rm.py`: Clarified irreversibility ("there is no trash; the bytes are gone").
  - `file_mv.py`: Added overwrite warning and path-confirmation guidance.
  - `file_search.py`: Uses "regex" instead of "pattern" in no-match message.
  - `worktree.py`: Entry message simplifies to path + branch only; exit message clarifies `keep_branch=False` is irreversible.
  - `delegate.py`: Worktree line in sub-agent envelope shortened.

- **Improvement: System context token-limit line removed**:
  - `system_context.py`: Token-limit-per-request line removed, dropping the `CFG` import. Token limits are model-specific; the model itself already knows its own context window.

- **Chore: Version bumped to 2.30.2a1**:
  - `pyproject.toml`: `2.30.1` → `2.30.2a1`.

- **Tests**:
  - `test/llm/lsp/test_server.py`: `get_diagnostics` test rewritten to assert against `textDocument/publishDiagnostics` push notification instead of pull-diagnostics response.
  - `test/llm/prompt/test_tool_guidance.py`: Assertions updated for plain-language section headings and no-emoji output.
  - `test/llm/tool/test_file.py`: All `write_file`/`replace_in_file` calls wrapped in `asyncio.run()` via `_w`/`_r` helpers.
  - `test/llm/tool/test_rag.py`: Assertion updated for new docstring format.

## 2.30.1 (May 25, 2026)

- **Chore: LLM challenges extracted to separate repo**:
  - `llm-challenges/` directory removed from the zrb repository. The evaluation framework (challenge definitions, experiment data, results, report) now lives in its own repository.

- **Improvement: Mandate completeness rule tightened**:
  - `mandate.md`: "Completeness" now explicitly requires deliverable files to land on disk via a Write or Edit tool call — printing content into chat, even in a fenced block, does not count.

- **Improvement: `file_edit.py` docstring**:
  - `replace_in_file()` gained a docstring documenting the post-edit validity requirement: if the change would leave the file malformed (broken indent, missing import, dangling brace), the caller should widen `old_text` or use Write to re-emit the whole file.

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

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)
