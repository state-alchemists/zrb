---
description: "A workflow for writing robust, safe, and maintainable shell scripts."
---
# Shell Scripting Guide

This guide is for writing robust, safe, and maintainable shell scripts.

## 1. The Non-Negotiable Boilerplate

Every script you write MUST start with this. No exceptions.

```bash
#!/usr/bin/env bash

# Exit on error, exit on unset variables, and exit on pipe fails.
set -euo pipefail
```

## 2. Core Principles

- **Safety First:** Always quote your variables (`"$VAR"`). Use `[[` instead of `[`. Check command success.
- **Readability:** Use clear variable names (`snake_case`). Add comments for anything complex. Use functions to structure your code.
- **Portability:** Prefer POSIX-compliant features when possible, but assume `bash` as a safe default unless otherwise specified.
- **Error Handling:** If a command can fail, you MUST check its exit code and handle the failure appropriately.

## 3. Best Practices

### Variable Safety
- **Quote Everything:** `rm "$file"` instead of `rm $file`.
- **Use Local Variables in Functions:** `local my_var="value"` to avoid polluting the global scope.
- **Use Arrays for Lists:** `args=("-a" "-b" "$file")` and `command "${args[@]}"` is safer than a single string.
- **Use `readonly` for Constants:** `readonly TIMEOUT=30`.

### Robust Commands
- **Check for Command Existence:** `if ! command -v jq &> /dev/null; then ...`
- **Handle Command Failures:** `my_command || { echo "my_command failed" >&2; exit 1; }`
- **Use `mktemp` for Temporary Files/Dirs:** `tmp_file=$(mktemp)` and `trap 'rm -f "$tmp_file"' EXIT`.

### Script Structure
- **`main` function:** Put your core logic in a `main()` function and call it at the end with `main "$@"`.
- **Logging Functions:** Create simple `log` and `error` functions to standardize output.
- **Usage/Help Function:** Every script should have a `usage()` function that explains what it does and what arguments it expects.

## 4. Linting

- All scripts MUST be checked with `shellcheck`. There should be no warnings.

## 5. Common Commands

- **Linting:** `shellcheck your_script.sh`
- **Executing:** `bash your_script.sh`
- **Debugging:** `bash -x your_script.sh`
