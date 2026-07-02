🔖 [Documentation Home](../../README.md) > [Task Types](./) > Built-in Helpers

# Built-in Helper Tasks

Zrb comes with a suite of pre-packaged, ready-to-use tasks for common developer operations. You don't need to write these from scratch — by default (`CFG.LOAD_BUILTIN` is `"on"`), simply `import zrb` and every built-in group is auto-registered and ready to run with zero extra code. You can still import individual tasks and bind them to your own `cli` group if you want custom grouping.

These are organized into conceptual modules within `zrb.builtin`.

---

## Table of Contents

- [Available Modules](#available-modules)
- [How to Use](#how-to-use-built-in-tasks)
- [Quick Reference](#quick-reference)

---

## Available Modules

> Each task below is registered under its group with a short **alias** as the
> actual CLI subcommand — e.g. the base64-encode task's internal name is
> `encode-base64`, but its alias is `encode`, so the runnable command is `zrb
> base64 encode` (not `zrb base64 encode-base64`). The **Command** column
> below always shows the real, runnable `zrb ...` invocation. The internal
> task name (used for `from zrb.builtin import ...`, see
> [Quick Reference](#quick-reference)) is only mentioned where it differs
> obviously from the alias.

### 📦 Base64 (`base64`)

Encode, decode, and validate base64 strings.

| Command | Description |
|---------|-------------|
| `zrb base64 encode` | Encode string to base64 (`--url-safe` for the `-_` alphabet) |
| `zrb base64 decode` | Decode base64 to string (`--url-safe` for the `-_` alphabet) |
| `zrb base64 validate` | Validate base64 string (accepts base64 of binary data, not only UTF-8 text) |

### ⚙️ Config (`config`)

Inspect runtime configuration.

| Command | Description |
|---------|-------------|
| `zrb config explain` | Render all `EnvField`-backed config knobs as a formatted terminal table (rich's `Table`, not markdown — env var, current value, description). Accepts optional `--keyword` to filter. |

### 🌱 Git (`git`)

Standard git operations wrapped as Zrb tasks.

| Command | Description |
|---------|-------------|
| `zrb git diff` | Show git diff between two branches/commits |
| `zrb git commit` | Stage all changes and create a commit |
| `zrb git pull` | Pull from remote |
| `zrb git push` | Push to remote |

### 🌿 Git Branch (`git branch`)

| Command | Description |
|---------|-------------|
| `zrb git branch prune` | Clean up merged/deleted local branches |

### 📝 Git Changelog (`git changelog`)

| Command | Description |
|---------|-------------|
| `zrb git changelog generate` | LLM-driven changelog generation, one file per matching git tag |

### 🌳 Git Subtree (`git subtree`)

Manage git subtrees easily.

| Command | Description |
|---------|-------------|
| `zrb git subtree add` | Add a git subtree |
| `zrb git subtree pull` | Pull from subtree |
| `zrb git subtree push` | Push to subtree |

### 🌐 HTTP (`http`)

Network utilities.

| Command | Description |
|---------|-------------|
| `zrb http request` | Send HTTP request; returns the response body (pipe-friendly). Supports `--body-format` (`json`/`form`/`raw`), `--params`, and `--timeout` |
| `zrb http curl` | Generate curl command from request setup |

### 🔐 JWT (`jwt`)

JSON Web Token operations.

| Command | Description |
|---------|-------------|
| `zrb jwt encode` | Create a JWT |
| `zrb jwt decode` | Decode and inspect a JWT's claims (no signature check by default; pass `--verify` with a secret to verify) |
| `zrb jwt validate` | Validate JWT signature |

### 🤖 LLM (`llm`)

AI assistant integration.

| Command | Description |
|---------|-------------|
| `zrb llm chat` (also available directly as `zrb chat`) | Start an interactive chat session with the configured LLM assistant |

### 🔑 MD5 (`md5`)

Hashing utilities. For other algorithms (SHA family) and HMAC, see the [`hash`](#-hash-hash) group below.

| Command | Description |
|---------|-------------|
| `zrb md5 hash` | Hash a string with MD5 |
| `zrb md5 sum` | Calculate file checksum |
| `zrb md5 validate` | Validate MD5 hash |

### 🧩 Hash (`hash`)

Hash text or files and compute HMACs with any `hashlib` algorithm (`sha256` default; also `sha1`, `sha224`, `sha384`, `sha512`, `md5`). Select with `--algorithm`.

| Command | Description |
|---------|-------------|
| `zrb hash hash` | Hash a string |
| `zrb hash sum` | Hash a file (streamed) |
| `zrb hash hmac` | Compute an HMAC of text with a secret key |

### 🕒 Time (`time`)

Convert between Unix epoch timestamps and ISO 8601. `--timezone` accepts `utc` (default) or `local`.

| Command | Description |
|---------|-------------|
| `zrb time now` | Show the current time as epoch and ISO 8601 |
| `zrb time to-iso` | Convert a Unix epoch to ISO 8601 |
| `zrb time to-epoch` | Convert an ISO 8601 datetime to a Unix epoch (naive input treated as UTC) |

### 🔗 URL (`url`)

| Command | Description |
|---------|-------------|
| `zrb url encode` | Percent-encode text for safe use in a URL |
| `zrb url decode` | Decode percent-encoded URL text |
| `zrb url parse` | Parse a URL into its components (as JSON) |

### 📦 JSON (`json`)

| Command | Description |
|---------|-------------|
| `zrb json format` | Pretty-print (indent) JSON |
| `zrb json minify` | Minify JSON |
| `zrb json validate` | Validate JSON |
| `zrb json get` | Extract a value by dotted path (e.g. `user.roles[0]`) |
| `zrb json to-yaml` | Convert JSON to YAML |
| `zrb json from-yaml` | Convert YAML to JSON |

### 🔤 Case (`case`)

| Command | Description |
|---------|-------------|
| `zrb case convert` | Convert between snake/camel/pascal/kebab/constant/title case (`--style`) |
| `zrb case slugify` | Turn text into a URL-friendly slug |

### 📅 Cron (`cron`)

| Command | Description |
|---------|-------------|
| `zrb cron parse` | Validate a cron expression and list its next run times (`--count`) |

### 🔣 Hex (`hex`)

| Command | Description |
|---------|-------------|
| `zrb hex encode` | Encode text to hexadecimal |
| `zrb hex decode` | Decode hexadecimal to text (tolerates spaces and a `0x` prefix) |
| `zrb hex dump` | Produce a hexdump (offset + hex + ASCII) of text |

### 🔢 Number (`number`)

| Command | Description |
|---------|-------------|
| `zrb number convert` | Convert a number between bases 2, 8, 10, and 16 |

### 🐍 Python (`python`)

| Command | Description |
|---------|-------------|
| `zrb python format` | Format code using `isort` and `black` (internal task name: `format-code`) |

### 🎲 Random (`random`)

| Command | Description |
|---------|-------------|
| `zrb random throw` | Simulate dice throws |
| `zrb random shuffle` | Randomize list orders |
| `zrb random password` | Generate a cryptographically secure password |
| `zrb random token` | Generate a secure URL-safe token |
| `zrb random string` | Generate a secure random alphanumeric string |

### 🔎 SearXNG (`searxng`)

Self-hosted meta search engine integration.

| Command | Description |
|---------|-------------|
| `zrb searxng start` | Start a local SearXNG instance on `--port` (default: `ZRB_SEARXNG_PORT`) |

### 🔧 Setup (`setup`)

Bootstrap developer tools on a fresh machine.

| Command | Description |
|---------|-------------|
| `zrb setup ubuntu` | Install common Ubuntu developer packages |
| `zrb setup asdf` | Install and configure `asdf` version manager |
| `zrb setup latex ubuntu` | Install LaTeX on Ubuntu (nested under a `latex` subgroup) |
| `zrb setup tmux` | Install and configure `tmux` |
| `zrb setup zsh` | Install and configure `zsh` with Oh My Zsh and zinit |

### 💬 Shell (`shell`)

All of these are nested under a `shell autocomplete` subgroup.

| Command | Description |
|---------|-------------|
| `zrb shell autocomplete bash` | Generate bash completion script |
| `zrb shell autocomplete zsh` | Generate zsh completion script |
| `zrb shell autocomplete powershell` | Generate PowerShell completion script |
| `zrb shell autocomplete subcmd` | List subcommands for shell completion |

### ✅ Todo (`todo`)

Todo.txt-compatible task management.

| Command | Description |
|---------|-------------|
| `zrb todo add` | Add a new todo item |
| `zrb todo list` | List todo items |
| `zrb todo show` | Search and display a todo item by keyword |
| `zrb todo complete` | Mark a todo item as done |
| `zrb todo archive` | Move completed items to archive |
| `zrb todo log` | Log work time against a todo item |
| `zrb todo edit` | Edit the raw todo.txt content |

### 🆔 UUID (`uuid`)

Identifier generation and validation. The top-level `uuid generate`/`uuid validate` default to UUID v4; each version also has its own nested subgroup.

| Command | Description |
|---------|-------------|
| `zrb uuid generate` | Generate a UUID v4 (random) |
| `zrb uuid validate` | Check UUID v4 validity |
| `zrb uuid v1 generate` / `zrb uuid v1 validate` | UUID v1 (time-based) generate/validate |
| `zrb uuid v3 generate` / `zrb uuid v3 validate` | UUID v3 (namespace + MD5) generate/validate |
| `zrb uuid v4 generate` / `zrb uuid v4 validate` | UUID v4 (random) generate/validate |
| `zrb uuid v5 generate` / `zrb uuid v5 validate` | UUID v5 (namespace + SHA-1) generate/validate |

### 🆔 ULID (`ulid`)

Universally Unique Lexicographically Sortable Identifier generation and validation.

| Command | Description |
|---------|-------------|
| `zrb ulid generate` | Create a ULID |
| `zrb ulid validate` | Check ULID validity |

---

## How to Use Built-in Tasks

To use a built-in task, import it from `zrb.builtin` and add it to your CLI or a specific group.

> **Note:** since these tasks are already auto-registered by default (see the
> [Available Modules](#available-modules) commands above), you'd normally
> only do this to set `CFG.LOAD_BUILTIN=off` and cherry-pick specific tasks,
> or to re-group them under your own custom group/alias. Adding a task
> directly with `add_task(task)` and no explicit `alias=` uses the task's
> internal name (e.g. `git-commit`), which is a different, additional command
> path from the one it already has in its default group (e.g. `zrb git
> commit`) — both work simultaneously once you've added it this way.

```python
from zrb import cli, Group
from zrb.builtin import (
    encode_base64,
    decode_base64,
    git_commit,
)

# Add directly to root
cli.add_task(git_commit)

# Or group utilities together
crypto_group = cli.add_group(Group(name="crypto"))
crypto_group.add_task(encode_base64)
crypto_group.add_task(decode_base64)
```

Now you can run:

```bash
zrb git-commit --message "Fixing bug"
zrb crypto encode-base64 --text "Hello World"
```

---

## Quick Reference

```python
from zrb.builtin import encode_base64, git_commit, http_request

# Import what you need
# Then add to CLI: cli.add_task(task_name)
```

| Module | Import Example |
|--------|---------------|
| base64 | `from zrb.builtin import encode_base64` |
| case | `from zrb.builtin import convert_case` |
| config | `from zrb.builtin import explain_config` |
| cron | `from zrb.builtin import parse_cron` |
| git | `from zrb.builtin import git_commit` |
| hash | `from zrb.builtin import hash_text` |
| hex | `from zrb.builtin import encode_hex` |
| http | `from zrb.builtin import http_request` |
| json | `from zrb.builtin import format_json` |
| jwt | `from zrb.builtin import encode_jwt` |
| llm | `from zrb.builtin import llm_chat` |
| md5 | `from zrb.builtin import hash_md5` |
| number | `from zrb.builtin import convert_base` |
| python | `from zrb.builtin import format_python_code` |
| random | `from zrb.builtin import throw_dice` |
| searxng | `from zrb.builtin import start_searxng` |
| setup | `from zrb.builtin import setup_ubuntu` |
| shell | `from zrb.builtin import make_bash_autocomplete` |
| time | `from zrb.builtin import epoch_to_iso` |
| todo | `from zrb.builtin import add_todo` |
| ulid | `from zrb.builtin import generate_ulid` |
| url | `from zrb.builtin import encode_url` |
| uuid | `from zrb.builtin import generate_uuid_v4` |

---

🔖 [Documentation Home](../../README.md) > [Task Types](./) > Built-in Helpers
