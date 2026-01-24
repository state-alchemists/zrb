🔖 [Home](../../README.md) > [Documentation](../README.md) > [Core Concepts](./README.md)

# Built-in Tasks

`zrb` comes with a rich set of built-in tasks that you can use in your projects. These tasks are designed to cover common use-cases and can be easily integrated into your workflows.

This document provides an overview of the available built-in tasks and their functionalities.

## Available Task Groups

### `base64`

Tasks for encoding and decoding base64 strings.

- `encode`: Encodes a string to base64.
- `decode`: Decodes a base64 string.
- `validate`: Validates if a string is a valid base64.

### `git`

Tasks for interacting with Git repositories.

- `diff`: Shows the differences between two branches, commits, or tags.
- `commit`: Commits changes to the repository.
- `pull`: Pulls changes from a remote repository.
- `push`: Pushes changes to a remote repository.
- `branch prune`: Deletes local branches that are not on the remote.

### `git subtree`

Tasks for managing Git subtrees.

- `add`: Adds a new subtree to the repository.
- `pull`: Pulls changes from a subtree.
- `push`: Pushes changes to a subtree.

### `http`

Tasks for making HTTP requests.

- `request`: Sends an HTTP request and prints the response.
- `curl`: Generates a `curl` command for a given request.

### `jwt`

Tasks for working with JSON Web Tokens (JWT).

- `encode`: Encodes a JWT.
- `decode`: Decodes a JWT.
- `validate`: Validates a JWT.

### `llm`

Tasks for interacting with Large Language Models.

- `chat`: 🤖 Interactive AI Assistant. Supports TUI, file attachments, session management, and more.

### `md5`

Tasks for calculating and validating MD5 hashes.

- `hash`: Calculates the MD5 hash of a string.
- `sum`: Calculates the MD5 checksum of a file.
- `validate`: Validates an MD5 hash.

### `python`

Tasks for Python development.

- `format`: Formats Python code using `isort` and `black`.

### `project`

Tasks for managing Zrb projects and applications.

- `add fastapp`: Adds a FastAPI-based application structure to your project.

### `random`

Tasks for generating random data.

- `throw`: Simulates throwing dice.
- `shuffle`: Shuffles a list of values.

### `shell`

Tasks for managing your shell environment.

- `autocomplete bash`: Generates Bash autocompletion scripts.
- `autocomplete zsh`: Generates Zsh autocompletion scripts.

### `todo`

Tasks for managing a `todo.txt` file.

- `add`: Adds a new task to the todo list.
- `list`: Lists all tasks in the todo list.
- `show`: Shows the details of a specific task.
- `complete`: Marks a task as complete.
- `archive`: Archives completed tasks.
- `log`: Logs work on a task.
- `edit`: Opens the `todo.txt` file for manual editing.

### `uuid`

Tasks for generating and validating UUIDs.

- `generate`: Generates a UUID v4.
- `v1 generate`: Generates a UUID v1.
- `v3 generate`: Generates a UUID v3.
- `v4 generate`: Generates a UUID v4.
- `v5 generate`: Generates a UUID v5.
- `validate`: Validates a UUID.
- `v1 validate`: Validates a UUID v1.
- `v3 validate`: Validates a UUID v3.
- `v4 validate`: Validates a UUID v4.
- `v5 validate`: Validates a UUID v5.

### `ulid`

Tasks for working with ULIDs (Universally Unique Lexicographically Sortable Identifiers).

- `generate`: Generates a new ULID.
- `validate`: Validates a ULID string.
