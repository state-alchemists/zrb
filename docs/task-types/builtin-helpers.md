🔖 [Documentation Home](../../README.md) > [Task Types](./) > Built-in Helpers

# Built-in Helper Tasks

Zrb comes with a suite of pre-packaged, ready-to-use tasks for common developer operations. You don't need to write these from scratch; simply import them and bind them to your `cli` group!

These are organized into conceptual modules within `zrb.builtin`.

## Available Modules

### 1. `base64`
Encode, decode, and validate base64 strings.
- `encode-base64`
- `decode-base64`
- `validate-base64`

### 2. `git`
Standard git operations wrapped as Zrb tasks.
- `git-diff`
- `git-commit`
- `git-pull`
- `git-push`
- `prune-local-git-branches`: Safely cleans up local branches that have been merged/deleted on the remote.

### 3. `git subtree`
Manage git subtrees easily.
- `add-git-subtree`
- `pull-git-subtree`
- `push-git-subtree`

### 4. `http`
Network utilities.
- `http-request`: Sends a request and prints the response.
- `generate-curl`: Generates a `curl` string equivalent for a given request setup.

### 5. `jwt`
JSON Web Token operations.
- `encode-jwt`
- `decode-jwt`
- `validate-jwt`

### 6. `md5`
Hashing utilities.
- `hash-md5` (String hashing)
- `sum-md5` (File checksums)
- `validate-md5`

### 7. `python`
- `format-python`: Formats code in the current directory using `isort` and `black`.

### 8. `random`
- `throw-dice`: Simulates dice throws.
- `shuffle`: Randomizes list orders.

### 9. `shell`
- `autocomplete-bash`: Generates a bash completion script for your Zrb CLI.
- `autocomplete-zsh`: Generates a zsh completion script.

### 10. `uuid` and `ulid`
Identifier generation and validation.
- UUID v1, v3, v4, v5 generation and validation.
- ULID generation and validation.

---

## How to use Built-in Tasks

To use a built-in task, import it from `zrb.builtin` and add it to your CLI or a specific group.

```python
from zrb import cli, Group
from zrb.builtin import (
    encode_base64_task, 
    decode_base64_task,
    git_commit_task
)

# Add directly to root
cli.add_task(git_commit_task)

# Or group utilities together
crypto_group = cli.add_group(Group(name="crypto"))
crypto_group.add_task(encode_base64_task)
crypto_group.add_task(decode_base64_task)
```

Now you can run:
```bash
zrb git-commit --message "Fixing bug"
zrb crypto encode-base64 --string "Hello World"
```
