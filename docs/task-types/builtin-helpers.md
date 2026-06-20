🔖 [Documentation Home](../../README.md) > [Task Types](./) > Built-in Helpers

# Built-in Helper Tasks

Zrb comes with a suite of pre-packaged, ready-to-use tasks for common developer operations. You don't need to write these from scratch; simply import them and bind them to your `cli` group!

These are organized into conceptual modules within `zrb.builtin`.

---

## Table of Contents

- [Available Modules](#available-modules)
- [How to Use](#how-to-use-built-in-tasks)
- [Quick Reference](#quick-reference)

---

## Available Modules

### 📦 Base64 (`base64`)

Encode, decode, and validate base64 strings.

| Task | Description |
|------|-------------|
| `encode-base64` | Encode string to base64 (`--url-safe` for the `-_` alphabet) |
| `decode-base64` | Decode base64 to string (`--url-safe` for the `-_` alphabet) |
| `validate-base64` | Validate base64 string (accepts base64 of binary data, not only UTF-8 text) |

### 🔀 Git (`git`)

Standard git operations wrapped as Zrb tasks.

| Task | Description |
|------|-------------|
| `git-diff` | Show git diff |
| `git-commit` | Create a commit |
| `git-pull` | Pull from remote |
| `git-push` | Push to remote |
| `prune-local-git-branches` | Clean up merged/deleted local branches |

### 🌳 Git Subtree (`git subtree`)

Manage git subtrees easily.

| Task | Description |
|------|-------------|
| `add-git-subtree` | Add a git subtree |
| `pull-git-subtree` | Pull from subtree |
| `push-git-subtree` | Push to subtree |

### 🌐 HTTP (`http`)

Network utilities.

| Task | Description |
|------|-------------|
| `http-request` | Send HTTP request; returns the response body (pipe-friendly). Supports `--body-format` (`json`/`form`/`raw`), `--params`, and `--timeout` |
| `generate-curl` | Generate curl command from request setup |

### 🔐 JWT (`jwt`)

JSON Web Token operations.

| Task | Description |
|------|-------------|
| `encode-jwt` | Create a JWT |
| `decode-jwt` | Decode and inspect a JWT's claims (no signature check by default; pass `--verify` with a secret to verify) |
| `validate-jwt` | Validate JWT signature |

### 🔑 MD5 (`md5`)

Hashing utilities. For other algorithms (SHA family) and HMAC, see the [`hash`](#-hash-hash) group below.

| Task | Description |
|------|-------------|
| `hash-md5` | Hash a string with MD5 |
| `sum-md5` | Calculate file checksum |
| `validate-md5` | Validate MD5 hash |

### 🧩 Hash (`hash`)

Hash text or files and compute HMACs with any `hashlib` algorithm (`sha256` default; also `sha1`, `sha224`, `sha384`, `sha512`, `md5`). Select with `--algorithm`.

| Task | Description |
|------|-------------|
| `hash-text` | Hash a string |
| `hash-file` | Hash a file (streamed) |
| `hash-hmac` | Compute an HMAC of text with a secret key |

### 🕒 Time (`time`)

Convert between Unix epoch timestamps and ISO 8601. `--timezone` accepts `utc` (default) or `local`.

| Task | Description |
|------|-------------|
| `now` | Show the current time as epoch and ISO 8601 |
| `epoch-to-iso` | Convert a Unix epoch to ISO 8601 |
| `iso-to-epoch` | Convert an ISO 8601 datetime to a Unix epoch (naive input treated as UTC) |

### 🔗 URL (`url`)

| Task | Description |
|------|-------------|
| `encode-url` | Percent-encode text for safe use in a URL |
| `decode-url` | Decode percent-encoded URL text |
| `parse-url` | Parse a URL into its components (as JSON) |

### 📦 JSON (`json`)

| Task | Description |
|------|-------------|
| `format-json` | Pretty-print (indent) JSON |
| `minify-json` | Minify JSON |
| `validate-json` | Validate JSON |
| `get-json` | Extract a value by dotted path (e.g. `user.roles[0]`) |
| `json-to-yaml` | Convert JSON to YAML |
| `yaml-to-json` | Convert YAML to JSON |

### 🔤 Case (`case`)

| Task | Description |
|------|-------------|
| `convert-case` | Convert between snake/camel/pascal/kebab/constant/title case (`--style`) |
| `slugify` | Turn text into a URL-friendly slug |

### 📅 Cron (`cron`)

| Task | Description |
|------|-------------|
| `parse-cron` | Validate a cron expression and list its next run times (`--count`) |

### 🔣 Hex (`hex`)

| Task | Description |
|------|-------------|
| `encode-hex` | Encode text to hexadecimal |
| `decode-hex` | Decode hexadecimal to text (tolerates spaces and a `0x` prefix) |
| `dump-hex` | Produce a hexdump (offset + hex + ASCII) of text |

### 🔢 Number (`number`)

| Task | Description |
|------|-------------|
| `convert-base` | Convert a number between bases 2, 8, 10, and 16 |

### 🐍 Python (`python`)

| Task | Description |
|------|-------------|
| `format-python` | Format code using `isort` and `black` |

### 🎲 Random (`random`)

| Task | Description |
|------|-------------|
| `throw-dice` | Simulate dice throws |
| `shuffle` | Randomize list orders |
| `generate-password` | Generate a cryptographically secure password |
| `generate-token` | Generate a secure URL-safe token |
| `generate-string` | Generate a secure random alphanumeric string |

### 💻 Shell (`shell`)

| Task | Description |
|------|-------------|
| `autocomplete-bash` | Generate bash completion script |
| `autocomplete-zsh` | Generate zsh completion script |
| `autocomplete-powershell` | Generate PowerShell completion script |

### 🆔 UUID (`uuid`)

Identifier generation and validation.

| Task | Description |
|------|-------------|
| UUID v1/v3/v4/v5 generate | Create UUIDs of various versions |
| UUID validate | Check UUID validity |

### 🆔 ULID (`ulid`)

Universally Unique Lexicographically Sortable Identifier generation and validation.

| Task | Description |
|------|-------------|
| ULID generate | Create a ULID |
| ULID validate | Check ULID validity |

---

## How to Use Built-in Tasks

To use a built-in task, import it from `zrb.builtin` and add it to your CLI or a specific group.

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
zrb crypto encode-base64 --string "Hello World"
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
| cron | `from zrb.builtin import parse_cron` |
| git | `from zrb.builtin import git_commit` |
| hash | `from zrb.builtin import hash_text` |
| hex | `from zrb.builtin import encode_hex` |
| http | `from zrb.builtin import http_request` |
| json | `from zrb.builtin import format_json` |
| jwt | `from zrb.builtin import encode_jwt` |
| md5 | `from zrb.builtin import hash_md5` |
| number | `from zrb.builtin import convert_base` |
| python | `from zrb.builtin import format_python_code` |
| random | `from zrb.builtin import throw_dice` |
| shell | `from zrb.builtin import make_bash_autocomplete, make_powershell_autocomplete, make_zsh_autocomplete` |
| time | `from zrb.builtin import epoch_to_iso` |
| ulid | `from zrb.builtin import generate_ulid` |
| url | `from zrb.builtin import encode_url` |
| uuid | `from zrb.builtin import generate_uuid_v4` |

---

🔖 [Documentation Home](../../README.md) > [Task Types](./) > Built-in Helpers
