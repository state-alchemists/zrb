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
| `encode-base64` | Encode string to base64 |
| `decode-base64` | Decode base64 to string |
| `validate-base64` | Validate base64 string |

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
| `http-request` | Send HTTP request and print response |
| `generate-curl` | Generate curl command from request setup |

### 🔐 JWT (`jwt`)

JSON Web Token operations.

| Task | Description |
|------|-------------|
| `encode-jwt` | Create a JWT |
| `decode-jwt` | Decode a JWT |
| `validate-jwt` | Validate JWT signature |

### 🔑 MD5 (`md5`)

Hashing utilities.

| Task | Description |
|------|-------------|
| `hash-md5` | Hash a string with MD5 |
| `sum-md5` | Calculate file checksum |
| `validate-md5` | Validate MD5 hash |

### 🐍 Python (`python`)

| Task | Description |
|------|-------------|
| `format-python` | Format code using `isort` and `black` |

### 🎲 Random (`random`)

| Task | Description |
|------|-------------|
| `throw-dice` | Simulate dice throws |
| `shuffle` | Randomize list orders |

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
| git | `from zrb.builtin import git_commit` |
| http | `from zrb.builtin import http_request` |
| jwt | `from zrb.builtin import encode_jwt` |
| md5 | `from zrb.builtin import hash_md5` |
| python | `from zrb.builtin import format_python_code` |
| random | `from zrb.builtin import throw_dice` |
| shell | `from zrb.builtin import make_bash_autocomplete, make_powershell_autocomplete, make_zsh_autocomplete` |
| ulid | `from zrb.builtin import generate_ulid` |
| uuid | `from zrb.builtin import generate_uuid_v4` |

---