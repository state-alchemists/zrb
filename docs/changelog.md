🔖 [Documentation Home](../README.md)


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
