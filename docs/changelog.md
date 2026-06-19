🔖 [Documentation Home](../README.md)

## 2.38.0 (June 19, 2026)

- **Feature: four more Claude-Code hook events** (`src/zrb/llm/hook/types.py`, `agent/run/runner.py`, `agent/run/error_classifier.py`, `tool/delegate.py`, ADR-0074):
  - **`PostCompact`** — fires after history summarization in `_prepare_history` (mirror of `PreCompact`), with `trigger="auto"`; honors `additionalContext`.
  - **`StopFailure`** — fires when a turn ends on an unrecoverable API error (before the exception propagates), observe-only. New `classify_error_type()` maps the exception to an `error_type` matcher token (`rate_limit`, `overloaded`, `server_error`, `context_length`, `authentication_failed`, `invalid_request`, `model_not_found`, `unknown`); new `HookContext.error_type` field.
  - **`SubagentStart` / `SubagentStop`** — fire around sub-agent delegation in `delegate.py::_run_agent_task` (both single and parallel paths; Stop fires in a `finally`), with `agent_type` (the delegated agent's name) and a shared `agent_id`. They fire on the **parent run's** hook manager via a new `current_hook_manager` ContextVar (set in `run_agent`, exposed by `runtime_state.get_current_hook_manager`, registered in `src/zrb/contextvars.py`), falling back to the module singleton.
  - Matcher fields added (`CLAUDE_EVENT_MATCHER_FIELDS`): `SubagentStart`/`SubagentStop` → `agent_type`, `StopFailure` → `error_type`, `PreCompact`/`PostCompact` → `trigger`. Claude `settings.json` configs using these events now register instead of being skipped as unknown.

- **Fix: `UserPromptSubmit` populates the `prompt` field** (`agent/run/runner.py`): the fire now passes `prompt=`, so UserPromptSubmit matchers (mapped to `prompt`), the `CLAUDE_PROMPT` env var, and the stdin payload see the submitted text — previously `None`.

- **Fix: close Claude-Code hook contract gaps for overlapping events** (`src/zrb/llm/agent/common.py`, `agent/run/deferred_calls.py`, `agent/run/runner.py`, `agent/run/session_extension.py`, `agent/run/hook_result_extractor.py`, `hook/hook_creators.py`, `hook/manager/manager.py`, `hook/types.py`, `hook/matcher.py`, `task/chat/task.py`; refines ADR-0074):
  - **`PreToolUse`/`PostToolUse`/`PostToolUseFailure` now carry the Claude-standard tool fields.** The fire sites pass `tool_name`/`tool_input` (and `tool_response` on `PostToolUse`, coerced to a JSON-safe dict by `_tool_response_payload`) as context kwargs. Previously these lived only in `event_data`, so the stdin payload omitted them — tool-name matchers (e.g. `{"matcher": "Bash"}`) silently never matched and hooks reading `tool_input` saw nothing.
  - **`exit 2` / `decision:"block"` only halts the hook chain for blocking-capable events** (new `BLOCKING_EVENTS` set in `types.py`). A block from a non-blocking event (e.g. `Notification`, `SessionStart`) no longer suppresses the remaining hooks for that event. `continue:false` still halts unconditionally.
  - **`PreCompact` can block compaction.** `_prepare_history` now checks `extract_block_decision` on the `PreCompact` results and skips the history processors (summarization) when blocked; the hard context-window prune still runs as a safety net.
  - **Raw stdout becomes `additionalContext` for `SessionStart`/`UserPromptSubmit`.** A command hook emitting unstructured stdout (not the JSON control protocol) has it injected as context, matching Claude; a JSON object is still respected verbatim.
  - **`PreToolUse` `permissionDecision: "ask"`/`"defer"` honored.** `"ask"` forces the interactive approval prompt (new `PreToolDecision.force_prompt` → `_resolve_approval(force_ask=…)`, overriding tool-policy/permission ALLOW and YOLO while still honoring an explicit DENY); `"defer"` is an explicit no-op. On the execution-time path (no prompt mechanism) `"ask"` degrades to proceed.
  - **`SessionEnd` gains matcher support and a real `source`.** `CLAUDE_EVENT_MATCHER_FIELDS` maps `SessionEnd` → `source`; the teardown fire passes `source="other"` (the single teardown point can't yet distinguish logout/prompt_input_exit).
  - **`continue:false` halts the `run_agent` turn loop.** New `extract_continue_decision`; `UserPromptSubmit` ends the turn before the model runs, and `Stop` ends it overriding any block-to-continue/`systemMessage` extension.

## 2.37.0 (June 19, 2026)

- **Fix: LSP tools now work with pyright and document-open-required servers** (`src/zrb/llm/lsp/server.py`, `manager/query_mixin.py`, `manager/symbol_utils.py`):
  - **Byte-accurate message framing** (`LSPServer._read_loop`): the read loop buffered a decoded `str` and sliced it by `Content-Length` (a *byte* count), and decoded each 4096-byte chunk individually. Any response containing non-ASCII (e.g. an em-dash in a diagnostic) or splitting a multi-byte char across a read boundary mis-framed or raised `UnicodeDecodeError`, killing the read loop and hanging every request — the root cause of pyright appearing to "not work." The loop now buffers bytes and decodes only complete message bodies.
  - **Documents are opened before file-scoped queries** (`LSPServer._ensure_open`): `goto_definition`, `find_references`, `document_symbols`, `hover`, and `rename` now `didOpen`/`didChange` the file (and wait briefly for initial analysis on first open) before issuing the request. Previously only `get_diagnostics` did this, so pyright/gopls/etc. returned empty for the others.
  - **`find_definition` uses `textDocument/definition`** instead of `workspace/symbol`: it locates the identifier's exact position and jumps to the definition — working on every server. `workspace/symbol` was unusable here (pyright returns nothing without indexing; pylsp doesn't implement it).
  - **`SymbolInformation` positions fixed** (`format_document_symbols`): flat `SymbolInformation` (pylsp) carries its position under `location.range`, not `range`/`selectionRange`. Reading the wrong field reported `line 1, col 0` for every symbol, breaking position lookups; both shapes are now handled. Symbol-position resolution also targets the identifier column, not column 0.
  - **`get_workspace_symbols` degrades gracefully**: when a server can't do a workspace-wide search it now falls back to the seed file's symbols filtered by the query (`scope: "file"`) instead of erroring.
  - **stderr is drained** so a verbose server (node/pyright) can't fill its stderr pipe and stall. Verified end-to-end against real pyright, pylsp, and gopls.

- **Feature: hook capability parity with Claude Code** (`src/zrb/llm/agent/common.py`, `src/zrb/llm/agent/run/`, `src/zrb/llm/hook/journal.py`, `src/zrb/llm/task/chat/task.py`, ADR-0074, refines ADR-0047/0066):
  - **Tool gates now fire for every tool call and honor the Claude protocol.** `create_agent` wraps the function-tools `FunctionToolset` so `SafeToolsetWrapper.call_tool` is the single chokepoint all tool calls pass through. `PreToolUse` fires there (guarded by pydantic-ai's `ctx.tool_call_approved` so deferred-then-approved calls don't double-fire) and honors `permissionDecision: "deny"` / exit-2 / `updatedInput` (arg rewrite); `PostToolUse` honors `decision: "block"` and `updatedToolOutput`; `PostToolUseFailure` fires when a tool raises. New extractors in `hook_result_extractor.py` (`extract_pre_tool_decision`, `extract_post_tool_decision`, `extract_permission_decision`, `extract_block_decision`) read `HookExecutionResult` and Claude's nested `hookSpecificOutput`.
  - **Turn control.** `UserPromptSubmit` can block a prompt (turn ends before the model runs). `Stop` is now the per-turn block-to-continue + extension point: a blocking `Stop` re-runs the agent with `reason` injected, capped at 8 consecutive blocks (mirrors `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`); the `systemMessage` turn-extension moved here from `SessionEnd` (`apply_session_end_extension` → `apply_turn_end_extension`).
  - **`PermissionRequest`** can auto-resolve an approval prompt via `decision.behavior` (`allow`/`deny`). **`PreCompact`** injects `additionalContext` and carries `trigger="auto"`. **`SessionStart`** carries `source` (`startup`/`resume`) for matchers.
  - **Breaking — `SessionEnd` is now terminal.** It fires once when the interactive chat session ends (`_teardown_interactive_resources`), not per turn. The built-in journaling reminder moved from `SessionEnd` to `Stop`. **Migration:** hooks that did journaling/summarization/turn-extension on `SessionEnd` must move to `Stop`; the proprietary `tool_args`/`cancel_tool` PreToolUse keys are removed in favor of `updatedInput`/`permissionDecision`.

## 2.36.0 (June 18, 2026)

- **Improvement: agent uses `WriteTodos` for multi-step work** (`src/zrb/llm/common_tools.py`, `src/zrb/llm/prompt/markdown/mandate.md`):
  - The `WriteTodos` tool guidance gained a quantified trigger (≥3 steps, multiple files, or multi-turn work — seed the list before the first edit) mirroring the `DelegateToAgent` style, replacing the vague "Planning a multi-step task". `GetTodos` guidance now also covers re-checking the plan after summarization.
  - The Working Loop's Plan step in `mandate.md` now wires the tool in explicitly: multi-step work externalizes its plan with `WriteTodos` rather than inline prose. Prompt-only; no tool/registration change.

- **Refactor: `DelegateToAgentsParallel` folded into `DelegateToAgent`** (`src/zrb/llm/tool/delegate.py`, ADR-0070):
  - `DelegateToAgent` gained an optional `tasks: list[dict]` argument; a non-empty list runs every entry concurrently (former parallel `asyncio.gather` path, now the module-level `_run_parallel` helper) and returns combined results, while the flat single-task call is unchanged. The standalone `DelegateToAgentsParallel` tool and `create_parallel_delegate_tool` factory are removed (also from `common_tools.py` guidance, `chat.py` factory/auto-approve, and `tool/__init__.py` exports).

- **Refactor: `ShellBackground` folded into `Shell`/`Bash` `background=True`** (`src/zrb/llm/tool/shell.py`, `bash.py`, `shell_background.py`, ADR-0071, supersedes ADR-0056 point 3):
  - `Shell`/`Bash` gained `background: bool = False` and `description: str = ""`; with `background=True` the call returns a handle immediately via the existing `_ShellBackgroundRegistry` (no timeout/streaming). The `ShellBackground` entry tool and `create_shell_background_tool` factory are removed; the registry and `MonitorProcess` are kept. Background launches now route through `bash_safe_command_policy` like any other shell call (the `auto_approve("ShellBackground")` entry is dropped).

- **Improvement: bounded `wait=`/`kill=` on background result-collection tools** (`src/zrb/llm/tool/delegate_background.py`, `shell_background.py`, `src/zrb/config/mixins/llm_limits.py`, ADR-0072, refines ADR-0054):
  - `GetDelegationResult` and `MonitorProcess` accept `wait: float = 0` — block up to `min(wait, CFG.LLM_BACKGROUND_WAIT_MAX)` seconds via `asyncio.wait` (which does not cancel on timeout), returning the instant the work finishes; on timeout they return a "still running — call again with wait=N or kill=True" status. `GetDelegationResult` also gained `kill: bool = False` for symmetry with `MonitorProcess`. New env var `LLM_BACKGROUND_WAIT_MAX` (`ZRB_LLM_BACKGROUND_WAIT_MAX`, default 300; in seconds, unlike the millisecond timeouts). A regression test confirms a background sub-agent's approval prompt still surfaces while a `wait=` call is parked.

- **Refactor: boolean config naming convention + `WEB_ENABLE_AUTH` → `WEB_AUTH_ENABLED`** (`src/zrb/config/mixins/web.py`, ADR-0073):
  - Codified the rule for boolean `CFG` knobs: `<namespace>_ENABLED` (state-last) for the master switch of a multi-setting namespace (groups with siblings like `WEB_AUTH_*`, `LLM_SANDBOX_*`, `HOOKS_*`); verb-first (`ENABLE_`/`SHOW_`/`SEARCH_`/`INCLUDE_`/`ALLOW_`) for standalone toggles (`LLM_ENABLE_BUILTIN_SKILLS`, `LLM_SEARCH_PROJECT`). Documented in `AGENTS.md` (Config Conventions) and ADR-0073.
  - `WEB_ENABLE_AUTH` was the lone violation (auth is a `WEB_AUTH_*` namespace) and is renamed to `WEB_AUTH_ENABLED`. The old `ZRB_WEB_ENABLE_AUTH` env key still works (read alias via `EnvField(aliases=[...], write_key="WEB_AUTH_ENABLED")`); writes use the new key. Docs and env-var tables updated with the legacy-alias note.

- **Feature: built-in LLM plugin split into governable categories** (`src/zrb/llm_plugin/`, ADR-0069):
  - The flat `llm_plugin/skills/` directory is split into `core_skills/` (the five `core-*` methodology skills the utility skills delegate into) and `skills/` (the eight utility skills). `agents/` is unchanged. Skills moved verbatim — frontmatter `name:` fields and `/slash-command` names are unchanged, so cross-references (e.g. `/testing` → `core-coding`'s testing companion) keep working.
  - **Core skills are always loaded and have no toggle** — disabling them would silently break the utility skills that depend on them.
  - Two new CFG booleans (default `on`) gate the optional built-in content: `LLM_ENABLE_BUILTIN_SKILLS` (`ZRB_LLM_ENABLE_BUILTIN_SKILLS`) and `LLM_ENABLE_BUILTIN_AGENTS` (`ZRB_LLM_ENABLE_BUILTIN_AGENTS`), added to `LLMSearchMixin` (`src/zrb/config/mixins/llm_search.py`) following the existing `LLM_SEARCH_PROJECT`/`LLM_SEARCH_HOME` pattern.
  - The toggles suppress **only built-in content** — user/project/plugin/extra skills and agents always load. `SkillManager._get_builtin_dir()` becomes `_get_builtin_dirs()` (CFG-filtered list); the agent `SearchMixin` wraps its built-in append in the agent toggle.
  - **Considered and rejected:** adding `dangerously_skip_sandbox` to the file tools (Read/Write/Edit/…). Claude Code keeps sandbox-escape a Bash-only concept and governs file access via the permission layer with no per-call bypass; zrb already mirrors this (escape stays on the OS-sandboxed shell tools; the Python FS gate from ADR-0063 has no escape, preserving credential deny-read protection).

## 2.35.3 (June 18, 2026)

- **Security: bumped 5 transitive dependency pins for GHSA advisories** (`pyproject.toml`):
  - PyJWT: `>=2.12.1` → `>=2.13.0` — **GHSA-xgmm-8j9v-c9wx** (CVE-2026-48526): JWT forgery via JWK-as-HMAC-secret confusion in multi-algorithm verifiers.
  - cryptography: `>=46.0.7` → `>=48.0.1` — **GHSA-537c-gmf6-5ccf**: out-of-bounds read via statically linked OpenSSL in pre-built wheels.
  - python-multipart: `>=0.0.27` → `>=0.0.30` — **GHSA-5rvq-cxj2-64vf** (CVE-2026-53539): quadratic-time DoS via `;` separators in `application/x-www-form-urlencoded` bodies.
  - starlette: `>=1.0.1` → `>=1.3.1` — **GHSA-82w8-qh3p-5jfq** (CVE-2026-54283): `request.form()` silently ignores `max_fields`/`max_part_size` for url-encoded bodies, enabling DoS.
  - aiohttp: `>=3.14.0` → `>=3.14.1` in `xai` and `voyageai` extras — **GHSA-xcgm-r5h9-7989** (CVE-2026-54274): incomplete WebSocket frame payloads bypass memory size limits.

- **Dependency: bumped pydantic-ai-slim upper bound and anthropic floor** (`pyproject.toml`):
  - pydantic-ai-slim: `<1.107.0` → `<1.108.0` (no API breakage in this range).
  - anthropic (extra): `>=0.105.0` → `>=0.108.0` (matches pydantic-ai-slim 1.107+ requirement).

- **Documentation: new "Programming the Agent" guide and `agent-in-pipeline` example**:
  - `docs/advanced-topics/programming-the-agent.md` — the map of every Python hook the agent exposes: custom tools, lifecycle hooks, permission policies, approval channels, model routing, dynamic prompt sections, history processors, and agent-as-pipeline-node. Dynamic prompt sections and history processors are documented in full (no other home).
  - `examples/agent-in-pipeline/` — runnable end-to-end example of an `LLMTask` wired between deterministic pipeline steps with an in-process custom tool.
  - `README.md` updated with a "Program Your AI Agent" section and restored `docs/` prefix on the CI/CD link.

- **Fix: `examples/web-auth` username clash with built-in super-admin** (`examples/web-auth/zrb_init.py`): renamed the demo "admin" user to "boss" to avoid colliding with the built-in `admin` super-admin that auto-creates when auth is enabled.

- **Documentation: breadcrumb and link fixes** (`docs/changelog-v1.md`, `docs/changelog-v2.md`, `docs/advanced-topics/sandbox.md`): corrected stale relative paths in breadcrumb footers.

## 2.35.2 (June 17, 2026)

- **Fix: non-interactive sessions defaulted to interactive-mode ContextVar, leaving the plan-mode gate un-gated** (`llm/task/chat/runner_mixin.py`, ADR-0067):
  - The 2.35.1 plan-mode hang fix (`llm/agent/run/deferred_calls.py:231`) guards hard-ASK resolution with `not get_interactive_mode()`, but `get_interactive_mode()` reads a `ContextVar` set by `system_context.py:270` from `ctx.input.interactive`. In `_run_non_interactive_session`, `session_input` carried `message`, `session`, `yolo`, `attachments`, and `model` — but not `interactive` — so `getattr(ctx.input, "interactive", True)` fell back to `True` and the guard never activated, leaving non-interactive sessions still hanging on hard-ASK approval gates (e.g. `ExitPlanMode`). `session_input` now includes `"interactive": False`, closing the gap.

## 2.35.1 (June 16, 2026)

- **Fix: `zrb chat --interactive false` no longer hangs on the plan-mode approval gate** (`llm/agent/run/deferred_calls.py`, ADR-0067):
  - `PLAN_MODE_POLICY` pins `ExitPlanMode` to a hard ASK (`llm/permission/policy.py`). In a non-interactive run the approval cascade still fell through to the `StdUI` stdin prompt (`tool_call/handler.py` → `ui/std_ui.py`) and blocked until the process timed out. `_resolve_approval` now resolves a hard ASK deterministically when `get_interactive_mode()` is `False`: auto-approve `ExitPlanMode` (the plan gate is a no-op without a user to read the plan — mirrors AskUserQuestion / ADR-0062) and deny any other approval-gated tool with an actionable message instead of blocking.
- **Improvement: plan mode is interactive-aware (defense in depth)**: the `EnterPlanMode` tool guidance (`llm/common_tools.py`), the `Interactive: no` system-context line (`llm/prompt/system_context.py`), and the "approval gate" rules in the `core-research`, `core-design`, and `research` skills (`llm_plugin/skills/`) now tell the model to skip plan mode and present the plan inline when there is no user to approve it — so a well-behaved model never reaches the gate.
- **Fix: command-hook timeout path no longer raises `'int' object can't be awaited`** (`llm/hook/hook_creators.py`): the timeout-kill branch did `await process.wait()` on a synchronous `subprocess.Popen`, whose `.wait()` returns an `int`; awaiting it raised `TypeError`, swallowed the original `TimeoutError`, and left the subprocess unreaped. It now reaps via `loop.run_in_executor(None, process.wait)`.
- **Performance: throttle the "Prepare tool parameters" spinner** (`llm/util/stream_response.py`): a slow model streaming thousands of tool-argument deltas previously repainted the spinner once per delta, flooding stdout (observed: 9k+ frames / 500 KB per turn) and adding per-frame write-syscall latency. The repaint is now capped at ~10×/sec via a monotonic-clock throttle; the carriage-return cleanup still fires on every delta.
- **Refactor: dead-code removal — `update_todo`/`clear_todos`, `from_yolo`, and 30+ unused symbols** (ADR-0068): a systematic caller-count audit identified ~50 symbols with zero production callers. The two architecturally significant removals are `update_todo`/`clear_todos` (subsumed by `write_todos` replacing the full list) and `from_yolo` (unused conversion helper). The remaining removals include `HookResult.allow`/`deny`/`ask`/`with_system_message`/`with_additional_context` convenience methods, `NoSaveHistoryManager`, `parse_hook_config`, `create_claude_compatible_result`, `is_opaque_validation_error`, `promote_markdown_headers`, `pluralize`, `summarize_text`, `set_tool_registry`, `shutdown_idle`, `get_terminal_width`, `get_uis`, `HTTPChatUI`, `choice_window`, `ScaleResult.note`, and LSP dataclasses (`Position`/`Range`/`Location`/`Diagnostic`/`DocumentSymbol`/`SymbolInformation`/`Hover`). The audit also flagged `register_section` and `BufferedOutputMixin` as zero-caller, but both were **kept**: `register_section` (ADR-0061) has a confirmed downstream client, and `BufferedOutputMixin` is used by `examples/chat-telegram/` and documented in `llm-custom-ui.md`. All hook call sites in production code, examples, and docs were updated to the inline `HookResult(success=True, modifications={...})` pattern. (`src/zrb/llm/tool/plan.py`, `src/zrb/llm/permission/policy.py`, `src/zrb/llm/hook/interface.py`, `src/zrb/llm/history_manager/no_save_history_manager.py`, `src/zrb/llm/hook/executor.py`, `src/zrb/llm/hook/hook_loader.py`, `src/zrb/llm/lsp/protocol.py`, `src/zrb/llm/lsp/manager/lifecycle_mixin.py`, `src/zrb/llm/lsp/manager/manager.py`, `src/zrb/llm/lsp/configs.py`, `src/zrb/llm/summarizer/text_summarizer.py`, `src/zrb/llm/task/llm_task.py`, `src/zrb/llm/tool_call/argument_formatter/util.py`, `src/zrb/llm/ui/default/selection_mixin.py`, `src/zrb/llm/util/image_scale.py`, `src/zrb/llm/util/clipboard.py`, `src/zrb/util/markdown.py`, `src/zrb/util/string/conversion.py`, `src/zrb/runner/chat/http_chat.py`, `src/zrb/llm/app/__init__.py`; docs and examples updated.)

## 2.35.0 (June 15, 2026)

- **Feature: new built-in developer-utility task groups** (`builtin/hash.py`, `builtin/datetime.py`, `builtin/url.py`, `builtin/json.py`, `builtin/case.py`, `builtin/cron.py`, `builtin/hex.py`, `builtin/number.py`, registered in `builtin/group.py` and `builtin/__init__.py`):
  - `hash` — `hash` (text), `sum` (file, streamed in 8 KiB chunks), and `hmac`, each over `sha256`/`sha1`/`sha224`/`sha384`/`sha512`/`md5` via `hashlib.new`. Generalizes the existing md5-only group.
  - `time` — `now`, `to-iso` (epoch→ISO 8601), and `to-epoch` (ISO 8601→epoch); naive ISO datetimes are interpreted as UTC.
  - `url` — `encode`/`decode` (percent-encoding) and `parse` (URL split into a JSON object of scheme/host/port/path/query/fragment).
  - `json` — `format`, `minify`, `validate`, `get` (dotted-path extraction, e.g. `user.roles[0]`), plus `to-yaml`/`from-yaml`.
  - `case` — `convert` (snake/camel/pascal/kebab/constant/title) and `slugify` (accent-stripping, URL-friendly).
  - `cron` — `parse` validates an expression and lists upcoming run times, reusing `zrb.util.cron.match_cron` (no new dependency).
  - `hex` — `encode`/`decode` (ASCII↔hex, tolerating spaces and a `0x` prefix) and `dump` (offset + hex + ASCII hexdump).
  - `number` — `convert` between bases 2/8/10/16.
  - All new tasks are stdlib/`pyyaml`-only, so no new runtime dependency was added.

- **Feature: secure random generators** (`builtin/random.py`): added `random password`, `random token` (`secrets.token_urlsafe`), and `random string`, all backed by the `secrets` module.

- **Feature: `core-coding` skill gains a runtime-debugging / observability companion** (`llm_plugin/skills/core-coding/`):
  - New `workflows/observability.md` companion for diagnosing a *running or deployed* system that can't be reproduced locally — distinct from the local-failure `workflows/debug.md` (which now cross-links it). Covers core dumps (`gdb`/`coredumpctl`, Go/Python specifics), memory & heap dumps (Java `jcmd`/MAT, Python `py-spy`/`tracemalloc`, Node heap snapshots, Go `pprof`), `kubectl` triage (exit-code reading — 137/OOMKilled, 139/SIGSEGV, CrashLoopBackOff — `--previous` logs, `kubectl debug`, `kubectl cp` to pull dumps), Grafana/Prometheus (RED/USE, PromQL for p99 / working-set / restarts), and Elasticsearch/Kibana (KQL, trace-id correlation, the `_search` API), chained metrics → logs → runtime → dump.
  - Two portable, read-only Python helper tools (stdlib only): `tools/k8s-triage.py` (one-shot pod/deployment triage — status, events, `--previous` + current logs, `top`, exit-reason guidance; accepts a pod, `deploy/<name>`, or `label=value` selector) and `tools/coredump-bt.py` (all-thread `gdb` backtrace from a `<binary> <core>` pair or `--systemd <exe|pid>` via `coredumpctl`). Registered as a trigger row in `core-coding/SKILL.md` and auto-discovered as companion files.

- **Improvement: JWT decode without a secret** (`builtin/jwt.py`): `jwt decode` now defaults to inspect-without-verify (the jwt.io workflow) — paste a token and read its claims with no secret. Pass `--verify` to check the signature. Well-known timestamp claims (`exp`/`iat`/`nbf`/`auth_time`) are printed in human-readable UTC alongside their raw values.

- **Improvement: `http request` returns a pipe-friendly body** (`builtin/http.py`): the task now returns `response.text` (was a `requests.Response`, which printed as `<Response [200]>` on stdout), so `zrb http request ... | jq` works. Decorations stay on stderr. Added `body-format` (`json`/`form`/`raw`), `params` (query string as JSON), and `timeout` inputs; `HEAD`/`OPTIONS` added to the method list.

- **Improvement: Base64 URL-safe alphabet and correct validation** (`builtin/base64.py`): `encode`/`decode`/`validate` accept `--url-safe` (`-_` alphabet). `validate` now checks true base64 well-formedness with `validate=True` instead of requiring the payload to be UTF-8 text, so base64 of binary data (images, gzipped blobs) validates correctly.

- **Improvement: Claude-Code command hooks (e.g. peon-ping) now work end-to-end** (`llm/hook/hook_creators.py`, `llm/hook/hook_loader.py`, `llm/hook/manager/loader_mixin.py`, `llm/agent/run/runner.py`):
  - **Event payload on stdin (ADR-0066).** `create_command_hook` now writes the Claude-shaped event JSON (`HookContext.to_claude_json()` — `hook_event_name`, `session_id`, `cwd`, `tool_name`, …) to the subprocess' stdin via `communicate(input=…)`. Stdin-driven hooks like peon-ping read `json.load(sys.stdin)["hook_event_name"]` and ignore env vars, so without this they never fired. The existing `CLAUDE_*` env vars are unchanged.
  - **`settings.json` is now a hook source.** `_collect_hook_paths` also reads `.claude/settings.json` and `.claude/settings.local.json` (project and home), where Claude Code — and drop-in tools like peon-ping — register their hooks. The nested `hooks` block is parsed by the existing `_parse_claude_format`; other settings keys are ignored.
  - **`Stop` fires on natural turn completion.** `run_agent` fires `HookEvent.STOP` when a turn finishes and control returns to the user, not only on manual interrupt from the TUI. This is the per-turn "done" signal completion sounds/notifications listen on. The deferred-wait path does not fire it, and manual interrupts still fire `Stop` from the TUI (no double-fire).
  - Unknown events in a Claude config (`SubagentStart`/`SubagentStop`, which zrb does not yet emit) are now skipped at `debug` level instead of warning on every load.
  - **`PermissionRequest` event + attention notifications** (`llm/hook/types.py`, `llm/agent/run/deferred_calls.py`, `llm/tool/ask.py`): added `HookEvent.PERMISSION_REQUEST`, fired from the approval cascade (`_resolve_approval`) exactly when a tool call reaches an interactive prompt — after every auto-resolve path (always-approve, tool/permission policy, YOLO), so it never fires for auto-approved calls. `AskUserQuestion` (auto-approved, so it skips that path) fires a `Notification` with `notification_type='elicitation_dialog'` from `ask_user_question`. Both ring peon-ping's `input.required` sound, so tool-approval and question prompts now notify you.
  - **Fix: command-hook working directory.** `create_command_hook` now `expanduser`s the cwd and falls back to the inherited cwd when the directory is missing, instead of passing it straight to `create_subprocess_shell`. The UI's `Notification` hook also no longer passes the *display* cwd (`~/zrb`, home collapsed to `~`) — which the OS cannot resolve — so hooks stopped failing with `[Errno 2] No such file or directory: '~/…'` on every streamed output chunk.
  - **Fix: async command hooks are truly fire-and-forget** (`llm/hook/manager/manager.py`): `execute_hooks` now dispatches `async` command hooks as detached tasks on the running event loop instead of inside the thread executor's short-lived `asyncio.run` loop (which cancelled them immediately) and then *awaiting* the subprocess. Previously every `async` peon hook — including the `Notification` hook that fires per streamed output chunk — blocked the executor up to its timeout, producing a storm of `Hook execution timed out after 10s` warnings and multi-second stalls per turn. They now return instantly and complete in the background.
  - **Fix: command-hook timeout is enforced.** `create_command_hook` wraps `communicate()` in `wait_for` and `kill()`s the subprocess on timeout. The thread-pool executor's own `wait_for` cannot interrupt a blocked worker thread, so a hook (or a child it forks, e.g. peon-ping's audio player) that hung used to block well past its configured timeout.
  - **Fix: hooks no longer register (and fire) twice** (`llm/hook/hook_loader.py`): `get_search_directories` now dedups by resolved path. `$HOME` is searched by both the home tier and the project upward-walk whenever cwd is under `$HOME`, so `~/.claude/*` hooks were discovered and registered twice — every event fired twice (e.g. two peon-ping toasts per prompt).
  - **Fix: hook floods no longer exhaust file descriptors or storm timeouts** (`llm/hook/manager/manager.py`, `llm/hook/hook_creators.py`, `llm/ui/default/output_mixin.py`): three reinforcing fixes after fire-and-forget hooks exposed a flood. (1) Fire-and-forget command hooks are now bounded — a semaphore caps concurrent subprocesses and a backlog ceiling sheds excess — so a burst can't spawn hundreds of `peon.sh` at once (`[Errno 24] Too many open files`) or back up a serialized tool into a `timed out after 10s` storm. (2) Injected `CLAUDE_*` env values are size-capped, so a large `event_data` (e.g. full message history on `SessionStart`/`Stop`/`SessionEnd`) no longer overflows the OS exec limit (`[Errno 7] Argument list too long`); the full payload still arrives on stdin. (3) The UI no longer fires a `Notification` hook per streamed output chunk — that conflated "output produced" with the Claude `Notification` event (attention/permission), spawning a subprocess per chunk for no benefit (peon-ping suppresses it as unrecognized). Genuine attention notifications fire at the right moments (`PermissionRequest`, `elicitation_dialog`).
  - **Fix: `ZRB_HOOKS_ENABLED` is honored as a global kill-switch** (`llm/hook/manager/manager.py`): the documented flag was defined but never read, so toggling it did nothing. `execute_hooks` now returns immediately — no hook fires and the filesystem is not scanned — when `CFG.HOOKS_ENABLED` is off (default stays `on`). `docs/configuration/llm-config.md` corrected (default `on`, not `1`).

- **Tests**: new coverage for every new built-in (`test_base64.py`, `test_case.py`, `test_cron.py`, `test_datetime.py`, `test_hash.py`, `test_hex.py`, `test_json.py`, `test_number.py`, `test_url.py`, plus `test_jwt.py` / `test_random.py` / `test_http.py` extensions) and for the hook changes (`test_functionality.py`: stdin payload, `settings.json` loading, async fire-and-forget non-blocking, timeout-kill, oversized-env drop, search-dir dedup; `test_deferred_calls.py` / `test_runner.py`: `PermissionRequest` / `Stop` / `Notification` firing).
  - **Hook test isolation**: a session-scoped autouse fixture in `test/conftest.py` (plus `test/llm/agent/run/conftest.py`) pins the module-level `hook_manager` singleton to no search dirs and reloads it, so the suite never discovers and spawns the developer's real `~/.claude` hooks (e.g. peon-ping) — which previously made runs crawl and hang asyncio's subprocess teardown. `test/llm/hook/test_executor.py`'s timeout test was shortened (~2s → ~0.3s) since the worker thread is non-cancellable and `shutdown(wait=True)` must join it.
  - **Build/test config**: `pyproject.toml` `norecursedirs` now excludes `examples/` (its scripts are demos, not part of the suite) and added the `httpx2` dev dependency; removed the redundant `examples/llm-hooks/test_hooks.py` (a never-collected demo whose scenarios are already covered by `test/llm/hook/`); `.coveragerc` omits skill tool scripts (`**/llm_plugin/skills/**/tools/*.py`), which are shipped agent-runtime content rather than unit-tested library code.

## 2.34.3 (June 12, 2026)

- **Build: migrate `pyproject.toml` to the PEP 621 `[project]` table** (`pyproject.toml`, `scripts/build_pypi_readme.py`, `zrb_init.py`):
  - Moved package metadata, runtime `dependencies`, `optional-dependencies` (extras), `scripts`, and `urls` out of `[tool.poetry.*]` into the standard `[project]` table. Only Poetry-specific keys (`exclude`, the `dev` dependency group, `build-system`) remain under `[tool.poetry]`. The two in-repo version readers were repointed from `["tool"]["poetry"]` to `["project"]`: `zrb_init.py` (`_VERSION`) and `scripts/build_pypi_readme.py` (which now also reads `["project"]["urls"]["repository"]`).
  - **Removed the aggregate `all` extra.** Under legacy `[tool.poetry.extras]` it referenced *extra names* (`bedrock`, `huggingface`, `xai`, `voyageai`) that Poetry silently ignored, so `pip install zrb[all]` never pulled boto3/botocore (the AWS SDK) and other extra-only packages; rewriting it as explicit requirements would just duplicate — and risk drifting from — every version pin (it had already lost the `langchain-core>=1.3.3` security floor). Since `poetry install --all-extras` installs every extra without a meta-extra and `install.sh` installs zrb with no extras, `all` was dropped entirely. pip users enumerate the extras they want (`pip install "zrb[rag,...,voyageai]"`).
  - Relocated the centralized security-pin comment block onto the transitive dependency that carries each pin, inline within its owning extra (`pyasn1` in `vertexai`; `aiohttp` in `xai`/`voyageai`; `langchain-core`/`langchain-text-splitters`/`langsmith` in `voyageai`).

- **Improvement: gate `poetry lock` on consistency in `project.sh`**:
  - `project.sh` ran a bare `poetry lock` on every shell `source`, which re-resolves the whole dependency graph from PyPI even when `poetry.lock` is already consistent — a multi-minute cost, made heavier by the now-complete `all` extra. The lock step now runs only when the fast hash-compare reports drift (`poetry check --lock >/dev/null 2>&1 || poetry lock`), so an unchanged setup skips the re-resolve entirely. The companion `~/borg/init-borg.sh` install step was given the same guard.

## 2.34.2 (June 11, 2026)

- **Performance: prompt caching restored via stable system prompt + per-turn `<live-context>`** (`prompt/system_context.py`, `prompt/manager.py`, `task/llm_task.py`, `agent/run/runner.py`, `agent/subagent/manager/manager.py`; ADR-0065):
  - The system prompt is sent ahead of the conversation history, so its bytes must be identical across turns for any provider's prefix cache to hit. The `system_context` section opened with a second-resolution `- Time:` line plus git status / pending todos / active worktree, all of which change every turn — diverging the prefix and forcing a full cache miss on every request (observed `prompt_cache_hit_tokens: 0`), including the growing conversation history.
  - Split `system_context` by lifecycle: it now renders only session-invariant facts (OS, CWD, project markers, tools, model identity) into the cached system prompt, plus a stable anchor explaining the `<live-context>` contract. The volatile per-turn state (time, git, todos, worktree, mode, interactivity) and the per-turn ambient-state wiring (session / interactive / stale-worktree) moved to a new `render_live_context()`.
  - `PromptManager.create_live_context()` wraps that body as `<live-context>…</live-context>`; `LLMTask.get_live_context()` renders it and `run_agent(live_context=…)` appends it to the end of the current user turn (`_append_live_context`, handling text / multimodal / empty turns). The block is append-only and frozen into history, so the system-prompt-plus-history prefix stays byte-stable and caches across turns.
  - Sub-agents are single-turn, so the block is folded back into their inherited system prompt (`_build_inherited_prompt`) when they inherit `system_context` — preserving prior behavior with no caching downside.

## 2.34.1 (June 11, 2026)

- **Fix: history manager memory leak** (`file_history_manager.py`): The in-RAM conversation cache grew unboundedly across a session. Added an LRU eviction cap (`_MAX_CACHED_CONVERSATIONS = 8`) with dirty-entry tracking so unsaved updates are never dropped. The `_dirty` set is cleared on `save()`; clean entries reload losslessly from disk on next access.

- **Fix: LSP project root cache unbounded growth** (`lifecycle_mixin.py`): The per-file project-root directory walk cache had no size bound. Added `_MAX_PROJECT_ROOT_CACHE = 4096` with oldest-entry eviction. Precision doesn't matter at this level — unboundedness does.

- **Fix: denial reason accepts arbitrarily large payloads** (`handler.py`, `response_handler/default.py`, `truncate.py`): A mis-submitted input (whole screen buffer, pasted document) entered the conversation history as a tool result. Added `truncate_chars(text, 500)` with a `...[TRUNCATED N chars]` marker in `src/zrb/util/truncate.py`, applied in both the inline approval handler and the default response handler.

- **Fix: Enter key with focus on output pane submits pane content** (`keybindings_mixin.py`): Tab/F6 puts focus on the read-only output buffer. Enter there would resolve a pending confirmation or submit the entire pane content (banner, help, transcript) as user input. Enter now unconditionally refocuses the input field when focus is elsewhere.

- **Feature: logged warning for empty custom prompt sections** (`manager.py`): When a name in `include_sections` / `ZRB_LLM_INCLUDE_SECTIONS` resolves as neither built-in, registered provider, nor existing markdown file, the section is now composed as empty (instead of the previous silent no-op) and a warning is logged or printed at compose time — so a misspelled section name is diagnosable.

- **Improvement: prompt system weight reduction** (30 files across `prompt/`, `tool/`, `tool_call/`, `common_tools.py`, `llm_plugin/agents/`, `llm_plugin/skills/`, `AGENTS.md`):
  - Stripped redundant usage instructions from tool docstrings and tool guidance that duplicate the Tool Usage Guide.
  - Shifted Skill Activation policy and authority rules from the skills catalogue into the centralized Operating Rules section (single source of truth).
  - Standardized activation language across all sub-agent definitions (code-reviewer, generalist, researcher) to reference the Operating Rules table rather than restating per-agent rules.
  - Removed duplicative `when_to_use`/`key_rule` entries where the tool name is self-describing; tightened remaining guidance to cross-tool choice logic only.
  - Replaced "activate before X" phrasing with "activate when the deliverable is X" across all skill descriptions, matching the Skill Activation table semantics.
  - Stripped "Deliver complete outputs" from persona (implied by the quality rules), "Wait for agreement" from persona (covered by the Working Loop Frame step), and other weight lines.
  - Removed obsolete `__doc__` reassignment in `delegate.py` (the docstring is already on the function) and outdated `Mandates` section in `code.py` (redundant with tool guidance).
  - Tightened delegation guidance: removed motivational framing around fidelity/cost; kept only the scope-clamp rule.
  - Clarified that `core-coding` companions are defaults, not absolutes — explicit project guidelines override them.
  - Updated `git-summary/SKILL.md` to: default to drafting only, commit/PR only on explicit request.
  - Reduced total prompt weight by ~143 lines (net diff: +253 -143).

## 2.34.0 (June 10, 2026)

- **Feature: arrow-key selection UI for AskUserQuestion**:
  - The default full-screen chat UI and `StdUI` now render `AskUserQuestion` as an interactive, arrow-key-selectable list (↑/↓ to move, Enter to confirm) instead of requiring the user to type an option number. Multi-select questions use Space to toggle; a synthetic "✎ Type my own answer…" row drops to free-text, and in multi-select the typed text is appended to the already-checked options.
  - New optional `UIProtocol.ask_user_choice(spec: ChoiceSpec)` method (`tool_call/ui_protocol.py`). `BaseUI.ask_user_choice` provides a default that formats the spec as numbered text and delegates to `ask_user`, so the web/`SimpleUI`/`MultiUI`/sub-agent paths keep the existing type-a-number behavior unchanged.
  - Default UI: new `SelectionMixin` (`ui/default/selection_mixin.py`) renders the widget as an in-layout `Float` (no nested prompt-toolkit `Application`); `ConfirmationMixin`'s queue was generalized to `(future, prompt, spec)` so text confirmations and choices share one serialization path. `tool/ask.py` builds a `ChoiceSpec` per question and routes through `ask_user_choice` (falling back to `ask_user` for UIs that predate it).
  - Presentation: the streamed `🧰` tool-call line suppresses `AskUserQuestion`'s (large) args payload (`util/stream_response.py`) since the widget renders it; the float is full-width with an opaque panel background and a highlight bar on the cursor row (`app/style.py`) so the streaming output behind it no longer bleeds through; the question is echoed into scrollback with its answer only on resolve (no duplicate while the widget is open).
  - Tests: `test/llm/ui/default/test_selection_mixin.py`, plus extended `test/llm/ui/test_std_ui.py`, `test/llm/tool/test_ask.py`, and `test/llm/util/test_stream_response.py`.

- **Feature: opt-in filesystem sandbox for LLM tool calls (ADR-0063)**:
  - New `zrb/llm/sandbox/` package: one `SandboxPolicy` drives two enforcement layers — a Python-level FS gate (`_sandbox_gate` in `agent/common.py`, right after `_permission_gate`) that blocks writes outside the writable roots (`EDIT`/`UNKNOWN` tools) and reads of credential directories (all tools), and an OS-level wrapper for `Shell`/`Bash`/`ShellBackground` (`sandbox-exec` + generated SBPL on macOS, `bwrap` on Linux). Network stays open in v1; off by default (`ZRB_LLM_SANDBOX_ENABLED=false`).
  - Config: `ZRB_LLM_SANDBOX_ENABLED` / `OS_SHELL` / `WRITABLE_PATHS` / `DENY_READ_PATHS` / `FALLBACK` / `ALLOW_ESCAPE` (new `LLMSandboxMixin`). Where no OS mechanism exists (Windows, Linux without bwrap), `FALLBACK=warn` runs unsandboxed with a visible warning, `deny` refuses — never silent.
  - Escape hatch: `dangerously_skip_sandbox` on the shell tools — never auto-approved (`bash_validation`/`auto_approve` always route it to a human), blockable via `ALLOW_ESCAPE=false`.
  - Plumbing mirrors permissions: `LLMTask(sandbox=...)`, `run_agent(sandbox_policy=...)`, `current_sandbox_policy` ContextVar (sub-agent inheritance).
  - Shell PID-tracking wrapper now falls back to `$$` when `ps` is unavailable (macOS Seatbelt cannot exec setuid binaries) and records the shell's own PID for exclusion under wrappers.
  - Docs: `docs/advanced-topics/sandbox.md`, sandbox section in `docs/configuration/llm-config.md`, ADR-0063. Tests: `test/llm/sandbox/` incl. platform-conditional integration tests (real Seatbelt/bwrap runs).

## 2.33.4 (June 10, 2026)

- **Fix: AskUserQuestion prompt never rendered (stuck at "waiting for confirmation")** (`ui/default/confirmation_mixin.py`): `ask_user` set `_current_confirmation` *before* appending the prompt, so the prompt hit `OutputMixin.append_to_output`'s buffer guard (pending-confirmation + thinking → buffer to avoid interleaving main-agent tokens) and was buffered away instead of shown. The user saw the `🧰` tool-call line and "waiting for confirmation" but no question. The prompt is now appended *before* marking the confirmation pending, in both `ask_user` and `_activate_next_confirmation`.

- **Fix: AskUserQuestion gated behind a redundant approval prompt** (`tool/ask.py`, `tool_call/always_approve.py`, `agent/run/deferred_calls.py`, ADR-0062): `AskUserQuestion` *is* the user interaction, but as a deferred tool it went through the approval cascade — asking "Allow tool execution?" before the question itself rendered. Auto-approval was only wired via a single `auto_approve("AskUserQuestion")` entry in `builtin/llm/chat.py`, so delegated sub-agents, the web/API runner, and bare `LLMTask`s still prompted (or left the question un-surfaced). Auto-approval is now **intrinsic to the tool**: it self-registers via `register_always_auto_approve("AskUserQuestion")`, and `_resolve_approval` honors that registry as Priority 0 in every path. The redundant `chat.py` entry was removed (single source of truth).

## 2.33.3 (June 8, 2026)

- **Fix: empty env var reaches typed cast and crashes** (`env_field.py`): An explicitly empty env var (e.g. `export ZRB_WEB_HTTP_PORT=`) would reach `int("")`/`to_boolean("")` and raise an opaque error. Empty is now treated the same as unset, falling back to the resolved default.

- **Fix: fnmatch pattern always matched basename against full path** (`content_transformer.py`): A bare pattern like `*.txt` was matched as `fnmatch(file_path, basename(file_path))`, comparing the full path against its basename, which always passed. Now correctly matches `basename(file_path) against the pattern.

- **Fix: concurrent agent runs share and clobber each other's plan/build mode** (`runner.py`, `state.py`): Without per-run ContextVar isolation, every run mutated the single import-time default `AgentModeState`, so concurrent web chat sessions and parallel sub-agents overwrote each other's mode. `enter_agent_mode_scope`/`exit_agent_mode_scope` now bind a fresh run-local state per run, with the final mode propagated back to the caller so in-run `/plan` switches persist.

- **Fix: backup rotation deletes the live history file** (`file_history_manager.py`): When a conversation name carries a timestamp suffix (e.g. `session-2024-03-18-10-30`), the main file matches the backup filename pattern and rotation sorts it oldest and deletes the live history. The main file is now excluded from backup rotation.

- **Fix: empty `old_text` in `replace_in_file` corrupts the file** (`file_edit.py`): `"" in content` is always `True`, so `str.replace` with an empty `old_text` inserts `new_text` between every character. Now rejected with a clear error message directing the user to `Write` instead.

- **Fix: bash validation misses multi-command injection vectors** (`bash_validation.py`): Bare `&` (covering `&&` too) was missing from dangerous substrings, so `ls & rm -rf x` auto-approved. Newlines and carriage returns were also missing, so multi-line payloads bypassed approval. Additionally, `env` was removed from safe prefixes since `env FOO=1 rm -rf x` runs an arbitrary command; only `printenv` remains allowlisted.

- **Fix: chat API routes skip authorization for `llm chat` access** (`chat_api_route.py`): Every chat API route authenticated the user but skipped the `can_access_task` gate that other task API routes enforce, letting unauthorized users reach the most powerful surface (tool/shell execution). Added `_forbid_if_unauthorized` guard to all routes.

- **Fix: `Session.result` returns stale value from first push** (`session.py`): Used `xcom.peek()` (queue front, oldest) instead of `xcom.get()` (latest), so a readiness-monitored re-execution returned the first run's result instead of the current one.

- **Fix: circular task dependency causes unbounded recursion** (`session.py`): `register_task` recursed through readiness checks, successors, fallbacks, and upstreams without cycle detection. Added path-scoped ancestor tracking that fails fast with a clear message on circular dependencies.

- **Fix: `HttpCheck` probe hangs forever on half-open endpoint** (`http_check.py`): `requests.request` was called without a timeout, so a TCP connection that opens but never responds would block the `to_thread` worker indefinitely. Now bound with `timeout=self._interval`.

- **Fix: SSH command injection via unsanitized interpolations** (`util/cmd/remote.py`): Password, host, user, port, and SSH key paths were double-quoted but not `shlex.quote`d, so any field containing `"`, `` ` ``, or `$(…)` could break out and inject arbitrary shell commands. All interpolated fields now use `shlex.quote`.

- **Fix: cron weekday mismatch between Python and cron conventions** (`util/cron.py`): Python's `weekday()` maps Monday=0..Sunday=6, while cron uses Sunday=0..Saturday=6, causing day-of-week scheduling off-by-one errors. Converted via `isoweekday() % 7`. Also fixed day-of-month/weekday semantics: when both fields are restricted cron uses OR; when one is wildcard the fields are ANDed.

- **Fix: `Xcom.get()` returns same value as `peek()` (oldest, not latest)** (`xcom.py`): `get()` used `self[0]` (queue front, same as `peek()`) instead of `self[-1]` (most recently pushed), so single-variable semantics returned stale values after readiness-monitored re-execution.

- **Tests**: new/expanded coverage in `test_env_field.py`, `test_content_transformer.py`, `test_file_history_manager.py`, `test_state_and_gate.py`, `test_file.py`, `test_bash_validation.py`, `test_chat_api.py`, `test_session.py`, `test_http_check.py`, `test_command.py`, `test_util_cron.py`, `test_xcom.py`.

## 2.33.2 (June 7, 2026)

> Note: the Windows shell paths below are unit-tested with mocks and reasoned from documented `cmd.exe` / PowerShell / `psutil` behavior, but **not yet verified on a real Windows host**.

- **Feature: copy / export conversation transcript**:
  - New `/copy` chat command: bare copies the full conversation transcript to the system clipboard; with a path argument it writes the transcript to a file. `/redirect` (bare) now copies the last AI response to the clipboard (previously file-only), while `/redirect <file>` keeps its save-to-file behavior.
  - New `copy_text()` in `llm/util/clipboard.py` uses the existing `pyperclip` backend with an **OSC 52** terminal-escape fallback (works over SSH; wraps the sequence for tmux/screen passthrough).
  - `history_formatter.py` gains a `full=True` export mode (no per-message/tool/arg truncation) and `extract_last_response_text()`, which recovers the last assistant response from replayed history — so `/copy` and bare `/redirect` work on a freshly loaded `chat --session <name>` before any live turn.
  - Tab-completion suggests `response-<timestamp>.txt` for `/redirect` and `transcript-<timestamp>.txt` for `/copy`. The command is configurable via `ZRB_LLM_UI_COMMAND_COPY` (`DEFAULT_LLM_UI_COMMAND_COPY` = `/copy`).

- **Fix: cross-platform shell execution for `Shell` / `Bash` / `ShellBackground`**:
  - The three LLM execution tools each maintained a separate, POSIX-only subprocess stack (`os.setsid` via `preexec_fn`, `os.killpg`, a `pgrep -g` PID-tracking wrapper). `ShellBackground` was outright broken on Windows — `preexec_fn=os.setsid` raises on the first call since `os.setsid` doesn't exist there. All three now converge on shared, cross-platform primitives in `util/cmd/command.py`: `start_new_session=True` (setsid on POSIX, ignored on Windows), `psutil`-based `terminate_process` / `kill_pid` for whole-tree teardown (replacing `os.killpg`), and a new `resolve_shell()` for shell+flag selection. `stdin` is now `DEVNULL`, so a command that reads stdin fails fast instead of hanging until the timeout.
  - `terminate_process` snapshots the process tree **before** signalling (children are reparented once the shell exits), sends a graceful terminate, waits a grace window, then force-kills survivors — so a child that outlives its shell is no longer leaked.

- **Fix: `Bash` now actually runs bash; `Shell` uses the configured shell**:
  - `Bash` (`bash.py`) had become a behavioral duplicate of `Shell` — it ran `/bin/sh` (POSIX) / `cmd.exe` (Windows), never bash. It now executes under `bash`, matching Claude Code's Bash-tool semantics (git-bash on Windows); many Claude skills assume a `Bash` tool by name. `Shell` now defaults to `CFG.SHELL` (the user's configured shell via `ZRB_SHELL` / `DEFAULT_SHELL`, else the detected current shell) and also accepts an explicit `shell=` argument. `resolve_shell` resolves the shell+flag once; since `get_current_shell()` is now existence-checked (below), this is safe on minimal/Windows hosts.

- **Fix: `get_current_shell()` resolves only to shells that actually exist** (`config/helper.py`):
  - It previously returned a hardcoded `"bash"` on POSIX (broken on a minimal Alpine image where only busybox `sh` exists) and an unconditional `"PowerShell"` on Windows. Now every candidate is verified with `shutil.which`: POSIX honors `$SHELL`-is-zsh only when zsh is installed, otherwise probes `bash` → `sh`; Windows prefers `pwsh` → `powershell`, falling back to `cmd`. This also fixes `CmdTask`, which derives its shell from `CFG.SHELL` → `get_current_shell()`.
  - Corrected the shell→flag maps in both `resolve_shell` (`command.py`) and `CmdTask._get_shell_flag` (`cmd_task.py`): `powershell` / `pwsh` use `-Command` (was the cmd.exe `/c`, which PowerShell rejects), and `cmd` uses `/c`.

- **Fix: package import `NameError`** (`common_tools.py`): a half-applied `run_shell_command` → `run_bash_command` rename left a dangling `bash_cmd` reference that broke importing `zrb`.

- **Tests**: new coverage in `test/util/cmd/test_command.py` (`resolve_shell`, `terminate_process`), `test/config/test_config.py` (Alpine `sh` fallback, Windows `pwsh`/`powershell`/`cmd` resolution, zsh-requested-but-absent fallback), and `test/llm/tool/test_shell.py` (OS-default path, a real bash-only `[[ … ]]` bashism, background-PID reporting, stdin-no-hang); `test/llm/tool/test_bash.py` updated for the bash-backed tool. For the copy/export feature: `test/llm/util/test_clipboard.py` (`copy_text` success, OSC 52 fallback, tmux passthrough, no-tty failure), `test/llm/util/test_history_formatter.py` (`full=True` disables truncation, `extract_last_response_text`), `test/llm/app/completion/` (response/transcript filename suggestions), and `test/llm/ui/base/test_commands_mixin.py` + `test/llm/ui/test_ui.py` (bare/path `/copy` and bare `/redirect` handlers).

## 2.33.1 (June 7, 2026)

- **Feature: ULID built-in tasks**:
  - New `zrb ulid generate` and `zrb ulid validate <id>` tasks (`src/zrb/builtin/ulid.py`), mirroring the existing `uuid` helpers. `generate-ulid` prints and returns a fresh ULID; `validate-ulid` reports whether its `id` input parses. Both are exported from `zrb.builtin` (`generate_ulid`, `validate_ulid`) for programmatic use, and the `ulid` group is documented in `builtin-helpers.md`. The `ulid` package is imported lazily inside each task (`# lazy: heavy third-party`).

- **Fix: `AnyContext` abstraction was missing `print_err`**:
  - `print_err` is implemented by the concrete context but was absent from the `AnyContext` abstract base, so it was invisible to type-checkers and to code written against the interface. Added the matching `@abstractmethod` signature (`stderr` default, `flush=True`) to `src/zrb/context/any_context.py`.

- **Fix: journal link convention is file-relative, not journal-root-relative**:
  - `core-journaling` documented links as "relative to the journal root", but `journal-lint.py` and the template examples already resolved them relative to the **containing file** (standard markdown semantics) — so a root-relative link like `technical/jwt.md` written from `projects/my-app.md` was silently flagged broken. Aligned the docs on the file-relative convention with correct `../`-climbing examples (`SKILL.md`, `templates/insight-note.md`, `templates/activity-entry.md`), and corrected a day-file backlink that pointed to the year index instead of the sibling month index.
  - `journal-lint.py`: documented the file-relative resolution rule, and broken-link errors now emit a hint suggesting the correct file-relative path when the target would have resolved under the old root-relative rule (e.g. `-> technical/jwt.md (target missing) — did you mean (../technical/jwt.md)?`).

- **Chore: removed dead group placeholders**:
  - `builtin/group.py`: dropped the unused `project` / `project add` / `project add fastapp` group placeholders (no remaining references; fastapp scaffolding registers its own entry points). Tidied the `ulid` group emoji (`🔢`→`🆔`).

- **Tests**: new `test/builtin/test_ulid.py` covering ULID generation and valid/invalid validation.

## 2.33.0 (June 6, 2026)

- **Feature: config-positioned custom prompt sections (ADR-0061)**:
  - A section name in `include_sections` (or the `ZRB_LLM_INCLUDE_SECTIONS` env var) that is **not** a built-in now resolves as a custom section composed at its configured position — letting downstreams add always-on, ordered sections without editing `PromptManager`. Resolution precedence is **built-in > registered provider > markdown file** (`src/zrb/llm/prompt/manager.py`).
  - New `PromptManager.register_section(name, provider)` registers a dynamic `Callable[[AnyContext], str]`, composed by calling it with the active context at compose time — for content that must reflect runtime state (current sprint, deploy target, live schema). A built-in name is never shadowed; re-registering a name overwrites the previous provider; return `""` to emit nothing. Mirrors the `add_tool_guidance` registration pattern (config selects/orders, code supplies behavior).
  - When no provider is registered, an unknown name resolves via `get_prompt(name)` (project-override → env → base-prompt-dir → package) with `{PLACEHOLDER}` substitution, so e.g. `company_context` loads `company_context.md`. A missing file resolves to `""` (harmless no-op — note an unknown/misspelled name is therefore silently empty).
  - Deliberately rejected resolving-and-exec'ing a `.py` file named by the section: it would turn a declarative, widely-copied config string into a code-execution trigger. Dynamic behavior is registered explicitly in Python; config only names and orders. See ADR-0061 (`docs/adr/07-llm-extension.md`).

- **Tests**: 6 new tests in `test/llm/prompt/test_manager.py` covering registered sections (dynamic composition, include-order positioning, precedence over a same-named markdown file, context pass-through, re-registration overwrite, and that a built-in name is never shadowed).

- **Documentation**: AGENTS.md ("LLM Prompt System") documents the custom-section precedence chain and `register_section`; ADR-0061 records the decision (refines ADR-0035, mirrors ADR-0043, contrasts ADR-0044).

- **Documentation: docs/examples accuracy sweep**:
  - Fixed broken snippets: `cli.add_task(...)` quickstart in `README.md`/`README.pypi.md` (one task per call); `@make_task(retry=…)`→`retries=` in `examples/async-task/`; removed the non-existent `Env(is_secret=…)` argument (Env has no such parameter — use a default and/or `PasswordInput`) across `make-task.md`, `basic-tasks.md`, `custom-tasks.md`, `file-ops.md`; added the missing `make_task` import and corrected `ctx.render()` to single-brace f-string syntax (it is not Jinja2) in `session-and-context.md` and `xcom-deep-dive.md`.
  - Corrected documented defaults: `ZRB_SEARXNG_LANG` (`en`→`en-US`), `ZRB_WEB_COLOR` (`amber`→empty). Bumped stale Docker image tags `2.26.8`→`2.33.0` in `installation.md` and `ci-cd.md`. Rewrote `examples/chat-minimal-ui/README.md` to match the actual `SimpleUI` implementation (was describing `BaseUI`).
  - Documented previously-undocumented config: TUI color styles (`ZRB_LLM_UI_STYLE_*`), `ZRB_HOOKS_DEBUG`, the repo/file-analysis token thresholds, and the `/btw`, `/plan`, `/rewind` chat commands.
  - Added a "Programmatic Prompt Customization" subsection to `llm-config.md` §4 covering the three previously user-undocumented `PromptManager` hooks (`add_prompt`/`append_prompt` middleware chain, `register_section`, and file-backed custom sections) — previously only in AGENTS.md/ADR-0061.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)
