🔖 [Documentation Home](../../README.md) > [Configuration](./) > Environment Variables

# General Environment Variables

Zrb can be heavily customized using environment variables. These control everything from log levels to default text editors, and even the appearance of the Web UI.

> **Note on White-labeling:** If you have customized `_ZRB_ENV_PREFIX` (e.g., in `__main__.py` for a custom CLI), remember to replace `ZRB_` with your custom prefix (e.g., `ACME_LOGGING_LEVEL`).

## Core Configuration

*   `ZRB_SHELL`: Sets the shell used by `CmdTask`.
    *   Default: Auto-detected based on your system (`zsh`, `bash`, `PowerShell`).
*   `ZRB_EDITOR`: Default text editor for interactive prompts (e.g., when editing multi-line input).
    *   Default: `nano`
    *   Possible values: Any installed text editor (`nvim`, `code`, `vim`, etc.).
*   `ZRB_LOGGING_LEVEL`: Controls the verbosity of Zrb's internal logs.
    *   Default: `WARNING`
    *   Possible values: `CRITICAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET`.
*   `ZRB_BANNER`: Custom ASCII art or text displayed when the Zrb CLI starts.
    *   Default: Standard Zrb ASCII art.
    *   Possible values: Any string (supports f-string formatting with `{VERSION}`).
*   `ZRB_ROOT_GROUP_NAME`: Sets the name of the root command group displayed in help menus.
    *   Default: `zrb`
*   `ZRB_ROOT_GROUP_DESCRIPTION`: Sets the description for the root command group.
    *   Default: `Your Automation Powerhouse`
*   `_ZRB_CUSTOM_VERSION`: Overrides the displayed Zrb version string. Note: This is an internal variable primarily for white-labeling.

## File Discovery & Loading

*   `ZRB_INIT_FILE_NAME`: The filename Zrb searches for (recursively up parent directories) to load tasks and groups.
    *   Default: `zrb_init.py`
*   `ZRB_INIT_SCRIPTS`: A colon-separated list of absolute paths to specific Python scripts that Zrb will *always* load, regardless of directory location.
*   `ZRB_INIT_MODULES`: A colon-separated list of Python modules that Zrb will force-load on startup.
*   `ZRB_LOAD_BUILTIN`: Controls whether Zrb's pre-packaged tasks (Git, UUID, base64, etc.) are loaded.
    *   Default: `1` (true)
*   `ZRB_WARN_UNRECOMMENDED_COMMAND`: Whether to show warnings for shell commands that might be considered unsafe or unrecommended.
    *   Default: `1` (true)

## Directories and Files

*   `ZRB_SESSION_LOG_DIR`: Directory where Zrb stores session-specific logs and history.
    *   Default: `~/.zrb/session`
*   `ZRB_TODO_DIR`: Directory where the `todo.txt` file (used by built-in `todo` tasks) is stored.
    *   Default: `~/todo`

### Todo List Specific
*   `ZRB_TODO_FILTER`: A filter string applied to `todo` task listings.
*   `ZRB_TODO_RETENTION`: How long completed `todo` items are kept before being archived (e.g., `2w` for 2 weeks, `1m` for 1 month).
    *   Default: `2w`

## Web UI Configuration (Experimental)

Zrb's experimental Web UI has dedicated configuration options.

*   `ZRB_WEB_HTTP_PORT`: The port on which the Zrb Web UI server listens.
    *   Default: `21213`
*   `ZRB_WEB_ENABLE_AUTH`: Set to `1` (true) to enable username/password authentication for the Web UI.
    *   Default: `0` (false)
*   `ZRB_WEB_SECRET_KEY`: A secret key used for generating and signing authentication tokens. **Crucial for production security.**
    *   Default: `zrb`
*   `ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`: Expiration time for access tokens in minutes. Default: `30`.
*   `ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES`: Expiration time for refresh tokens in minutes. Default: `60`.
*   `ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME`: Cookie name for the access token. Default: `access_token`.
*   `ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME`: Cookie name for the refresh token. Default: `refresh_token`.
*   `ZRB_WEB_GUEST_USERNAME`: Username for guest users. Default: `user`.
*   `ZRB_WEB_SUPER_ADMIN_USERNAME`: Username for the super admin account. Also supports `ZRB_WEB_SUPERADMIN_USERNAME`. Default: `admin`.
*   `ZRB_WEB_SUPER_ADMIN_PASSWORD`: Password for the super admin account. Also supports `ZRB_WEB_SUPERADMIN_PASSWORD`. Default: `admin`.
*   `ZRB_WEB_TITLE`: Title displayed in the browser tab for the Web UI.
    *   Default: `Zrb`
*   `ZRB_WEB_JARGON`: A tagline or motto displayed on the Web UI homepage.
    *   Default: `Your Automation PowerHouse`
*   `ZRB_WEB_HOMEPAGE_INTRO`: Introductory text for the Web UI homepage.
    *   Default: `Welcome to Zrb Web Interface`
*   `ZRB_WEB_FAVICON_PATH`: Path to a custom favicon for the Web UI.
*   `ZRB_WEB_CSS_PATH`: Colon-separated list of paths to custom CSS files to apply to the Web UI.
*   `ZRB_WEB_JS_PATH`: Colon-separated list of paths to custom JavaScript files to apply to the Web UI.
*   `ZRB_WEB_COLOR`: A Pico CSS theme color to use for the Web UI (e.g., `amber`, `red`, `blue`). See [Pico CSS docs](https://picocss.com/docs/version-picker) for options.

## Interactive Editing (Diff tools)

*   `ZRB_DIFF_EDIT_COMMAND`: Template command used when the LLM assistant asks you to interactively edit a file replacement (e.g., in YOLO-off mode). Zrb uses this to launch a diff editor.
    *   Default: Automatically generated based on your `ZRB_EDITOR` with support for `code` (VSCode), `cursor`, `zed`, `emacs`, `nvim`/`vim`, falling back to `vimdiff`.
    *   Template variables: `{old}` (path to a temporary file with the original content), `{new}` (path to a temporary file with the new content).

---
