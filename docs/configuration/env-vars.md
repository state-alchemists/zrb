🔖 [Documentation Home](../../README.md) > [Configuration](./) > Environment Variables

# General Environment Variables

Zrb can be heavily customized using environment variables. These control everything from log levels to default text editors, and even the appearance of the Web UI.

> **Note on White-labeling:** If you have customized `_ZRB_ENV_PREFIX` (e.g., in `__main__.py` for a custom CLI), remember to replace `ZRB_` with your custom prefix (e.g., `ACME_LOGGING_LEVEL`).

---

## Table of Contents

- [Core Configuration](#core-configuration)
- [File Discovery & Loading](#file-discovery--loading)
- [Directories and Files](#directories-and-files)
- [Web UI Configuration](#web-ui-configuration-experimental)
- [Interactive Editing](#interactive-editing-diff-tools)

---

## Core Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_SHELL` | Shell used by `CmdTask` | Auto-detected (`zsh`, `bash`, `PowerShell`) |
| `ZRB_EDITOR` | Default text editor for interactive prompts | `nano` |
| `ZRB_LOGGING_LEVEL` | Verbosity of Zrb's internal logs | `WARNING` |
| `ZRB_BANNER` | Custom ASCII art or text displayed at CLI start | Standard Zrb ASCII art |
| `ZRB_ROOT_GROUP_NAME` | Name of root command group in help menus | `zrb` |
| `ZRB_ROOT_GROUP_DESCRIPTION` | Description for root command group | `Your Automation Powerhouse` |
| `_ZRB_CUSTOM_VERSION` | Overrides displayed version string (internal) | — |

> 💡 **Logging Levels:** `CRITICAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET`

> 💡 **Banner Formatting:** Supports f-string formatting with `{VERSION}`

---

## File Discovery & Loading

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_INIT_FILE_NAME` | Filename to search for (recursive up parent directories) | `zrb_init.py` |
| `ZRB_INIT_SCRIPTS` | Colon-separated list of Python scripts to always load | — |
| `ZRB_INIT_MODULES` | Colon-separated list of Python modules to force-load on startup | — |
| `ZRB_LOAD_BUILTIN` | Whether to load pre-packaged tasks (Git, UUID, base64, etc.) | `1` (true) |
| `ZRB_WARN_UNRECOMMENDED_COMMAND` | Show warnings for potentially unsafe shell commands | `1` (true) |

---

## Directories and Files

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_SESSION_LOG_DIR` | Directory for session-specific logs and history | `~/.zrb/session` |
| `ZRB_TODO_DIR` | Directory for `todo.txt` file | `~/todo` |

### Todo List Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_TODO_FILTER` | Filter string applied to `todo` task listings | — |
| `ZRB_TODO_RETENTION` | How long completed items are kept before archiving | `2w` |

> 💡 **Retention Format:** Use `2w` for 2 weeks, `1m` for 1 month, etc.

---

## Web UI Configuration (Experimental)

Zrb's experimental Web UI has dedicated configuration options.

### Server Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_HTTP_PORT` | Port for Web UI server | `21213` |
| `ZRB_WEB_ENABLE_AUTH` | Enable username/password authentication | `0` (false) |
| `ZRB_WEB_SECRET_KEY` | Secret key for authentication tokens ⚠️ **Change for production!** | `zrb` |

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
| `ZRB_WEB_SUPER_ADMIN_USERNAME` | Super admin username (also supports `ZRB_WEB_SUPERADMIN_USERNAME`) | `admin` |
| `ZRB_WEB_SUPER_ADMIN_PASSWORD` | Super admin password (also supports `ZRB_WEB_SUPERADMIN_PASSWORD`) | `admin` |

> ⚠️ **Security Warning:** Change default credentials before deploying to production!

### Appearance

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_TITLE` | Browser tab title | `Zrb` |
| `ZRB_WEB_JARGON` | Tagline displayed on homepage | `Your Automation PowerHouse` |
| `ZRB_WEB_HOMEPAGE_INTRO` | Introductory text on homepage | `Welcome to Zrb Web Interface` |
| `ZRB_WEB_FAVICON_PATH` | Path to custom favicon | — |
| `ZRB_WEB_CSS_PATH` | Colon-separated list of custom CSS file paths | — |
| `ZRB_WEB_JS_PATH` | Colon-separated list of custom JavaScript file paths | — |
| `ZRB_WEB_COLOR` | Pico CSS theme color (`amber`, `red`, `blue`, etc.) | — |

> 💡 **Theme Colors:** See [Pico CSS docs](https://picocss.com/docs/version-picker) for available color options.

---

## Interactive Editing (Diff Tools)

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_DIFF_EDIT_COMMAND` | Template command for interactive file editing (used by LLM assistant) | Auto-generated based on `ZRB_EDITOR` |

> **Template Variables:**
> - `{old}` — Path to temporary file with original content
> - `{new}` — Path to temporary file with new content

> 💡 **Supported Editors:** `code` (VSCode), `cursor`, `zed`, `emacs`, `nvim`/`vim`, falling back to `vimdiff`

---

## Quick Reference

```bash
# Essential settings
export ZRB_LOGGING_LEVEL=DEBUG          # Verbose logging
export ZRB_EDITOR=nvim                  # Use neovim for editing
export ZRB_INIT_FILE_NAME=tasks.py      # Use custom init file name

# Web UI (production)
export ZRB_WEB_ENABLE_AUTH=1
export ZRB_WEB_SECRET_KEY="your-secure-secret-key"
export ZRB_WEB_SUPER_ADMIN_PASSWORD="secure-password"

# Disable builtin tasks for cleaner environment
export ZRB_LOAD_BUILTIN=0
```

---