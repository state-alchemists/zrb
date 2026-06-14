🔖 [Documentation Home](../README.md)

## 2.35.0 (June 14, 2026)

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

- **Improvement: JWT decode without a secret** (`builtin/jwt.py`): `jwt decode` now defaults to inspect-without-verify (the jwt.io workflow) — paste a token and read its claims with no secret. Pass `--verify` to check the signature. Well-known timestamp claims (`exp`/`iat`/`nbf`/`auth_time`) are printed in human-readable UTC alongside their raw values.

- **Improvement: `http request` returns a pipe-friendly body** (`builtin/http.py`): the task now returns `response.text` (was a `requests.Response`, which printed as `<Response [200]>` on stdout), so `zrb http request ... | jq` works. Decorations stay on stderr. Added `body-format` (`json`/`form`/`raw`), `params` (query string as JSON), and `timeout` inputs; `HEAD`/`OPTIONS` added to the method list.

- **Improvement: Base64 URL-safe alphabet and correct validation** (`builtin/base64.py`): `encode`/`decode`/`validate` accept `--url-safe` (`-_` alphabet). `validate` now checks true base64 well-formedness with `validate=True` instead of requiring the payload to be UTF-8 text, so base64 of binary data (images, gzipped blobs) validates correctly.

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
