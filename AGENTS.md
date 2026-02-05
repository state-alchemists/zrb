# Zrb Project Guide for Agents

This document provides context and guidelines for LLMs (Agents) working with the `zrb` (Zaruba) project. Zrb is a Python-based task automation tool that integrates shell commands, Python functions, and LLM capabilities into a unified workflow.

## 1. Project Overview

-   **Name:** Zrb (Zaruba)
-   **Purpose:** Task automation and workflow orchestration.
-   **Core Language:** Python.
-   **Key Feature:** Built-in LLM integration for generating code and documentation.
-   **Execution:** CLI (`zrb task-name`) or Web UI (`zrb server start`).

## 2. Core Concepts

### 2.1. The `zrb_init.py` File
-   **Role:** The entry point for defining tasks.
-   **Location:**
    -   **Project-local:** `./zrb_init.py` (Applies to the current project).
    -   **Global:** `~/zrb_init.py` (Applies system-wide).
-   **Discovery:** Zrb automatically detects and loads this file.

### 2.2. Tasks (`Task`)
The fundamental unit of work. Common types include:
-   **`CmdTask`**: Executes shell commands.
-   **`Task` (or `BaseTask`)**: Executes Python code.
-   **`LLMTask`**: Interactions with LLMs.
-   **`HttpCheck` / `TcpCheck`**: Readiness checks for services.

### 2.3. Groups (`Group`)
-   Used to organize tasks hierarchically.
-   Example: `zrb deployment build` (`deployment` is the group, `build` is the task).

### 2.4. Context (`ctx`)
The execution context passed to every task.
-   **`ctx.input`**: User inputs (arguments).
-   **`ctx.env`**: Environment variables.
-   **`ctx.print()`**: Standard output method.
-   **`ctx.xcom`**: Cross-communication storage.

## 3. Defining Tasks (The "How-To")

### 3.1. Standard Shell Command (`CmdTask`)
Use this for running CLI tools.

```python
from zrb import CmdTask, cli

cli.add_task(
    CmdTask(
        name="hello-world",
        cmd="echo Hello World",
        description="Prints hello world"
    )
)
```

### 3.2. Python Function (`@make_task`)
Preferred for pure Python logic.

```python
from zrb import make_task, cli

@make_task(group=cli, name="greet", description="Greets a user")
def greet(ctx):
    name = ctx.input.name or "World"
    ctx.print(f"Hello, {name}!")
```

### 3.3. Task with Inputs and Env
Always define inputs and envs explicitly for better CLI/UI support.

```python
from zrb import CmdTask, StrInput, Env, cli

cli.add_task(
    CmdTask(
        name="deploy",
        cmd="echo Deploying to $TARGET_ENV with user $DEPLOY_USER",
        input=[
            StrInput(name="user", default="admin", description="Deployment user")
        ],
        env=[
            Env(name="TARGET_ENV", default="staging", link_to_os=True)
        ]
    )
)
```

### 3.4. Task Chaining (Dependencies)
-   `>>` (Sequential): `task_a >> task_b` (A runs, then B).
-   `<<` (Upstream): `task_b << task_a` (B depends on A).

```python
build >> test >> deploy
```

## 4. Configuration

Zrb is configured via environment variables (in `.env` or OS).

-   **Primary LLM Model:** `ZRB_LLM_MODEL` (e.g., `openai:gpt-4o`, `deepseek:deepseek-reasoner`, `ollama:llama3.1`).
-   **Small LLM Model:** `ZRB_LLM_SMALL_MODEL` (e.g., `openai:gpt-4o-mini`) - used for summarization and auxiliary tasks.
-   **API Keys:** `ZRB_LLM_API_KEY`, `OPENAI_API_KEY`, etc.
-   **Base URL:** `ZRB_LLM_BASE_URL` - for custom endpoints or local LLM servers.
-   **Prompt Directory:** `ZRB_LLM_PROMPT_DIR` (default: `.zrb/llm/prompt`).
-   **Plugin Directories:** `ZRB_LLM_PLUGIN_DIRS` - colon-separated paths to custom plugin directories containing agents and skills.

**Note on Provider Prefixes:** Zrb supports built-in providers via `pydantic-ai`. When specifying models, use the format `provider:model-name` (e.g., `deepseek:deepseek-reasoner`, `ollama:llama3.1`). Built-in providers include OpenAI, Anthropic, Google, DeepSeek, Groq, Mistral, and Ollama.

## 5. Common Patterns & Best Practices

1.  **Prefer `CmdTask` for Shell Operations:** Do not use `subprocess` in Python tasks if a `CmdTask` can do the job.
2.  **Use `ctx.print`:** Avoid `print()` to ensure output is captured and formatted correctly by Zrb.
3.  **Explicit Inputs:** Define `Input` objects instead of parsing `sys.argv` manually.
4.  **Readiness Checks:** Use `readiness_check` (`HttpCheck`, `TcpCheck`) for tasks that depend on services (e.g., waiting for a DB or Server).

## 6. Directory Structure

```
/
├── zrb_init.py          # Main task definition file
├── .env                 # Environment variables
├── .zrb/                # Zrb internal/config storage
│   └── llm/
│       └── prompt/      # Custom LLM prompts
└── ...

---

## 7. LLM Extension Architectural Patterns

When extending Zrb's LLM capabilities (e.g., adding hooks, new managers, etc.), follow these established patterns:

### 7.1. Classic Python Classes
Avoid using Pydantic's `BaseModel` for internal data structures or configurations. Use "classic" Python classes or `dataclasses`. This keeps the core lightweight and avoids dependency-heavy inheritance patterns.

### 7.2. Module-Level Singletons
Managers (like `SkillManager`, `NoteManager`, or `HookManager`) should be instantiated as singletons at the module level.
-   Define the manager class.
-   Create an instance at the bottom of the file (e.g., `hook_manager = HookManager()`).
-   Import this instance where needed.

### 7.3. Configuration and Path Conventions
-   Always use `CFG.ROOT_GROUP_NAME` when defining default configuration or storage paths.
-   Prefer paths like `.{CFG.ROOT_GROUP_NAME}/something` over hardcoded `.zrb/something`.
-   Discovery logic should check:
    1.  User home directory (`~/.{CFG.ROOT_GROUP_NAME}/...`)
    2.  Project-local directories (climbing up from CWD to root, checking `.{CFG.ROOT_GROUP_NAME}/...`)
    3.  Custom directories defined in `CFG`.

### 7.4. Lazy Loading and Scanning
Managers should have a `scan()` or `load()` method to discover artifacts, rather than doing it automatically in the constructor. This allows more control over when potentially heavy I/O operations occur.

---

## 8. Keeping This Guide Updated

This guide should be updated whenever significant changes are made to Zrb's architecture, configuration, or usage patterns. If you notice any information in this guide that is outdated or no longer relevant, please update it to ensure accuracy for future AI assistants working with the Zrb project.

Key areas to keep current:
- Configuration options and environment variables
- Task definition patterns and best practices
- Directory structure and file locations
- Core concepts and terminology
```
