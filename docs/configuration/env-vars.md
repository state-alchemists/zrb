🔖 [Documentation Home](../README.md) > [Configuration](./) > Environment Variables

# General Environment Variables

Zrb can be heavily customized using environment variables. These control everything from log levels to default text editors, and even the appearance of the Web UI.

> This page is about Zrb's *own* config knobs (read via the `CFG` singleton). Looking for how to define environment variables for *your own tasks* instead? See [Core Concepts: Environments (Envs)](../core-concepts/environments.md).

> This page covers the general knobs; the LLM, chat TUI and voice ones are in [LLM & Rate Limiter Configuration](./llm-config.md). `zrb config explain` (optionally `--keyword <text>`) prints every setting with its current value and description.

> **Note on White-labeling:** If you have customized `_ZRB_ENV_PREFIX` (e.g., in `__main__.py` for a custom CLI), remember to replace `ZRB_` with your custom prefix (e.g., `ACME_LOGGING_LEVEL`).

## Mistakes fail fast

`zrb_init.py` is configured by assigning to `CFG` directly, so two common mistakes are caught at the assignment itself rather than surfacing as a silent no-op or a confusing error somewhere else:

- Assigning a name `CFG` doesn't define (`CFG.LLM_MODELL = "..."`, a typo) raises `AttributeError` naming the closest real knob.
- Assigning a value the setting can't accept (`CFG.LLM_MAX_REQUEST_PER_MINUTE = "not-a-number"`) raises `ValueError` right there, not on the next unrelated read.

A mistyped *environment variable* is caught too, as a warning when zrb starts: `ZRB_LLM_MODELL is not a setting and is ignored. Did you mean ZRB_LLM_MODEL?`. Only a near miss of a real setting is reported, since a project's own `ZRB_*` variables read by its `zrb_init.py` are not typos.

A *retired* setting still in your environment is named at startup too, with what replaces it: `ZRB_LLM_VOICE_MODE is no longer read and is ignored. Set ZRB_LLM_DICTATION_BACKEND instead.` The full list is in `src/zrb/config/retired.py`; the [Upgrading Guide](../advanced-topics/upgrading-guide.md) explains each change.

---

## Table of Contents

- [Core Configuration](#core-configuration)
- [File Discovery & Loading](#file-discovery--loading)
- [Directories and Files](#directories-and-files)
- [Task Runtime](#task-runtime)
- [CLI Semantic Colors](#cli-semantic-colors)
- [Web UI Configuration](#web-ui-configuration-experimental)
- [Interactive Editing](#interactive-editing-diff-tools)

---

## Core Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_SHELL` | Shell used by `CmdTask` | Auto-detected: `zsh` when it is your `$SHELL`, else `bash`, else `sh`; on Windows a POSIX shell such as Git Bash, else PowerShell, else `cmd` |
| `ZRB_EDITOR` | Default text editor for interactive prompts | `nano` |
| `ZRB_IS_TERMUX` | Whether zrb runs under Termux (auto-detected; override for Termux-specific keybindings) | Auto-detected |
| [`ZRB_LOGGING_LEVEL`](../advanced-topics/logging.md) | Verbosity of Zrb's internal logs | `WARNING` |
| `ZRB_BANNER` | Custom ASCII art or text displayed at CLI start | Standard Zrb ASCII art |
| `ZRB_ROOT_GROUP_NAME` | Name of root command group in help menus | `zrb` |
| `ZRB_ROOT_GROUP_DESCRIPTION` | Description for root command group | `A coding agent with a built-in task DAG` |
| `_ZRB_CUSTOM_VERSION` | Overrides displayed version string (internal) | — |

> 💡 **Logging Levels:** See the [Logging Guide](../advanced-topics/logging.md) for details. `CRITICAL`, `FATAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET` (an unknown value means `WARNING`)

> 💡 **Banner Formatting:** Supports f-string formatting with `{VERSION}`

---

## File Discovery & Loading

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_INIT_FILE_NAME` | Name of the task-definition file zrb auto-loads. On startup zrb walks from the current directory up to the filesystem root and loads every file with this name it finds. | `zrb_init.py` |
| `ZRB_INIT_SCRIPTS` | Colon-separated (semicolon on Windows) Python script paths zrb runs on startup (in addition to the discovered `ZRB_INIT_FILE_NAME` files) to register task definitions | — |
| `ZRB_INIT_MODULES` | Comma-separated importable module names zrb imports on startup so their task definitions register (colon-separated still accepted) | — |
| `ZRB_INIT_STRICT` | Exit non-zero when any init module or script fails to load, instead of reporting it and starting anyway. `auto` resolves to off at a terminal and on everywhere else | `auto` |
| `ZRB_ENABLE_BUILTIN_TASKS` | Whether to load pre-packaged tasks (Git, UUID, base64, etc.) | `on` |
| `ZRB_SHOW_UNRECOMMENDED_COMMAND_WARNING` | Have `CmdTask` warn about non-portable or unsafe shell constructs in a `bash`/`zsh` script (`which`, `source`, `eval`, `echo -e`, …) | `on` (true) |
| `ZRB_SECRET_ENV_PATTERNS` | Comma-separated name fragments marking an env var as secret. Matched case-insensitively as a substring, so `KEY` covers `OPENAI_API_KEY`. Matching values are shown as `***` in `CmdTask`'s DEBUG environment dump. Empty string redacts nothing | `KEY,SECRET,TOKEN,PASSWORD,PASSWD,CREDENTIAL,AUTH,PRIVATE,SIGNATURE,SALT` |
| `ZRB_MCP_CONFIG_FILE` | Path to the MCP server config file | `mcp-config.json` |

> 💡 **A broken init file is reported, not hidden — and not fatal.** If a discovered `zrb_init.py`, an `ZRB_INIT_SCRIPTS` entry, or an `ZRB_INIT_MODULES` entry raises while loading, zrb prints the file, the line and the exception type to stderr, then continues: whatever that source already did before failing stays in effect, the rest of startup (further init sources, then the CLI itself) still runs, and the printed error is what tells you to fix it and rerun.

> ⚠️ **Unattended, that default turns itself around.** Continuing is the right call at a prompt, where you can read the error and rerun. It is the wrong call for an unattended run: an init file that raises *after* registering a task leaves the task callable, so `zrb deploy` succeeds and exits `0` against configuration that was never finished. `ZRB_INIT_STRICT` therefore defaults to `auto`, which reads stderr: a terminal means someone is watching the error, anything else (CI, cron, a piped run) means nobody is, and zrb aborts. Either way it still attempts every init source and reports each failure — so one run tells you about all of them — before exiting `1`.
>
> Set it explicitly to override the reading in both directions:
>
> ```bash
> ZRB_INIT_STRICT=1      # always fatal, even at a terminal
> ZRB_INIT_STRICT=off    # never fatal, even in CI
> ZRB_INIT_STRICT=auto   # the default
> ```

---

## Directories and Files

| Variable | Description | Default |
|----------|-------------|---------|
| [`ZRB_SESSION_LOG_DIR`](../advanced-topics/logging.md#session-log-directory) | Directory for session-specific logs and history | `~/.zrb/session` |
| [`ZRB_SESSION_LOG_RETENTION`](../advanced-topics/logging.md#session-log-directory) | How long a session's log is kept (`0` = keep all) | `30d` |
| [`ZRB_SESSION_LOG_PRUNE_INTERVAL`](../advanced-topics/logging.md#session-log-directory) | How often session-log retention is enforced per directory (`0` = every process) | `1d` |
| `ZRB_TODO_DIR` | Directory for `todo.txt` file | `~/todo` |

### Todo List Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_TODO_FILTER` | Filter string applied to `todo` task listings | — |
| `ZRB_TODO_RETENTION` | How long completed items are kept before archiving | `2w` |

> 💡 **Retention Format:** Use `2w` for 2 weeks, `1m` for 1 month, etc.

---

## Task Runtime

Timings for the task engine itself. Values are in **milliseconds** unless the row says otherwise.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_SHUTDOWN_TIMEOUT` | Graceful web server shutdown timeout (ms) | `10000` |
| `ZRB_CMD_CLEANUP_TIMEOUT` | Time to wait for a process to exit after interrupt before killing (ms) | `2000` |
| `ZRB_TASK_READINESS_TIMEOUT` | Default readiness-wait timeout for any task that does not set `readiness_timeout` itself; bounds the initial wait and each monitoring re-check round. `0` disables the cap, so a check that never returns hangs the run (ms) | `60000` |
| `ZRB_SCHEDULER_TICK_INTERVAL` | How often the Scheduler task checks its cron pattern (ms) | `60000` |
| `ZRB_HTTP_CHECK_INTERVAL` | Default polling interval for `HttpCheck` tasks (ms) | `5000` |
| `ZRB_TCP_CHECK_INTERVAL` | Default polling interval for `TcpCheck` tasks (ms) | `5000` |
| `ZRB_TASK_READINESS_DELAY` | Initial delay before starting readiness checks (ms) | `500` |
| `ZRB_CMD_BUFFER_LIMIT` | Asyncio subprocess read-buffer limit in bytes | `102400` |

---

## CLI Semantic Colors

ANSI colors for plain terminal output (outside the TUI). Each `_COLOR_*` value is a color name (`black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, or their `bright_*` variants). Each `_STYLE_*` value is a style name (`bold`, `faint`, `italic`, `underline`, `blink_slow`, `blink_fast`, `reversed`, `hide`, `crossed_out`). Leave a variable unset (or set to `""`) to suppress that attribute.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_CLI_COLOR_MUTED` | Foreground color for de-emphasized output | _(none)_ |
| `ZRB_CLI_STYLE_MUTED` | Style for de-emphasized output | `faint` |
| `ZRB_CLI_COLOR_WARNING` | Foreground color for warning messages | `yellow` |
| `ZRB_CLI_STYLE_WARNING` | Style for warning messages | `bold` |
| `ZRB_CLI_COLOR_ERROR` | Foreground color for error messages | `red` |
| `ZRB_CLI_STYLE_ERROR` | Style for error messages | `bold` |
| `ZRB_CLI_COLOR_SUCCESS` | Foreground color for success messages | `green` |
| `ZRB_CLI_STYLE_SUCCESS` | Style for success messages | _(none)_ |
| `ZRB_CLI_COLOR_HIGHLIGHT` | Foreground color for highlighted text (session names, commands) | `yellow` |
| `ZRB_CLI_STYLE_HIGHLIGHT` | Style for highlighted text | `bold` |
| `ZRB_CLI_COLOR_INFO` | Foreground color for informational messages | `cyan` |
| `ZRB_CLI_STYLE_INFO` | Style for informational messages | _(none)_ |
| `ZRB_CLI_COLOR_TODO_PROJECT` | Color for todo project tags (`+project`) | `yellow` |
| `ZRB_CLI_COLOR_TODO_CONTEXT` | Color for todo context tags (`@context`) | `cyan` |
| `ZRB_CLI_COLOR_TODO_KEYVAL` | Color for todo key:value pairs | `magenta` |

> These affect `stylize_warning`, `stylize_error`, `stylize_muted` (alias: `stylize_faint`/`stylize_log`), `stylize_highlight`, `stylize_info`, `stylize_success`, and the `stylize_todo_*` helpers. Physical helpers (`stylize_yellow`, `stylize_red`, etc.) are unaffected — they always produce their named color.

`ZRB_THEME` (see [LLM Configuration → Themes](./llm-config.md#themes-zrb_theme)) supplies the defaults for these knobs; an individual export still wins.

---

## Web UI Configuration (Experimental)

Zrb's experimental Web UI has dedicated configuration options.

### Server Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_HTTP_HOST` | Host/interface the Web UI server binds to ⚠️ **Non-loopback exposes the server to the network** | `127.0.0.1` |
| `ZRB_WEB_HTTP_PORT` | Port for Web UI server | `21213` |
| `ZRB_WEB_AUTH_ENABLED` | Enable username/password authentication | `off` |
| `ZRB_WEB_SECRET_KEY` | Secret key for authentication tokens ⚠️ **Change for production!** | `zrb` |
| `ZRB_WEB_AUTH_SECURE_COOKIES` | Set the `Secure` flag on auth cookies (HTTPS-only). Turn `off` for plain-HTTP non-localhost deployments where browsers would otherwise drop the cookies | `on` |

### Authentication Tokens

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiration time | `30` |
| `ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token expiration time | `60` |
| `ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME` | Cookie name for access token | `access_token` |
| `ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME` | Cookie name for refresh token | `refresh_token` |

### User Accounts

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_GUEST_USERNAME` | Username for guest users | `user` |
| `ZRB_WEB_SUPER_ADMIN_USERNAME` | Super admin username | `admin` |
| `ZRB_WEB_SUPER_ADMIN_PASSWORD` | Super admin password | `admin` |

> ⚠️ **Security Warning:** Change default credentials before deploying to production!

### Pagination

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_SESSION_PAGE_SIZE` | Default page size for chat session listings | `20` |
| `ZRB_WEB_API_PAGE_SIZE` | Default page size for generic API list endpoints | `20` |
| `ZRB_WEB_TASK_SESSION_PAGE_SIZE` | Default page size for task session listings | `10` |

### Appearance

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_TITLE` | Browser tab title | `Zrb` |
| `ZRB_WEB_JARGON` | Tagline displayed on homepage | `Coding Agent + Task Engine` |
| `ZRB_WEB_HOMEPAGE_INTRO` | Introductory text on homepage | `Welcome to Zrb Web Interface` |
| `ZRB_WEB_FAVICON_PATH` | Path to custom favicon | `/static/favicon-32x32.png` |
| `ZRB_WEB_CSS_PATH` | Colon-separated (semicolon on Windows) list of custom CSS file paths | — |
| `ZRB_WEB_JS_PATH` | Colon-separated (semicolon on Windows) list of custom JavaScript file paths | — |
| `ZRB_WEB_COLOR` | Pico CSS theme color name (`amber`, `red`, `blue`, etc.) — selects a bundled `pico.<color>.min.css`, so it is a name, not a CSS color value | — |

> 💡 **Theme Colors:** See [Pico CSS docs](https://picocss.com/docs/version-picker) for available color options.

---

## Interactive Editing (Diff Tools)

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_DIFF_EDIT_COMMAND` | Template command for interactive file editing (used by LLM assistant) | Auto-generated based on `ZRB_EDITOR` |

> **Template Variables:**
> - `{old}` — Path to temporary file with original content
> - `{new}` — Path to temporary file with new content

> 💡 **Supported Editors:** `code`/`vscode`, `vscodium`, `windsurf`, `cursor`, `zed`/`zeditor`, `agy`, `emacs`, `nvim`/`vim`, falling back to `vimdiff`

---

## Quick Reference

```bash
# Essential settings
export ZRB_LOGGING_LEVEL=DEBUG          # Verbose logging
export ZRB_EDITOR=nvim                  # Use neovim for editing
export ZRB_INIT_FILE_NAME=tasks.py      # Use custom init file name
export ZRB_INIT_STRICT=1                # Always fail the run if an init file breaks

# Web UI (production)
export ZRB_WEB_AUTH_ENABLED=1
export ZRB_WEB_SECRET_KEY="your-secure-secret-key"
export ZRB_WEB_SUPER_ADMIN_PASSWORD="secure-password"

# Disable builtin tasks for cleaner environment
export ZRB_ENABLE_BUILTIN_TASKS=0
```

---