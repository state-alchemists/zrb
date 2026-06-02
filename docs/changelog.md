🔖 [Documentation Home](../README.md)


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
