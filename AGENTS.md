# Zrb Agent Guide

## 1. Overview
Zrb (Zaruba) is a Python-based task automation tool and library.
- **Core Logic:** `src/zrb/`
- **Built-in Tasks:** `src/zrb/builtin/` (Pre-defined tasks users run via CLI)
- **LLM Integration:** `src/zrb/llm/` (Agents, Tools, Prompts)

## 2. Directory Structure & Navigation

### 2.1. Core Library (`src/zrb/`)
| Path | Description |
| :--- | :--- |
| `builtin/` | **Task Definitions**. Logic for `zrb <group> <task>` commands. Example: `builtin/searxng/start.py` defines `zrb searxng start`. |
| `config/` | **Configuration**. See `config.py` for `CFG` singleton and defaults. |
| `llm/tool/` | **LLM Tools**. Python functions callable by the LLM. Example: `llm/tool/search/searxng.py` implements the `search_internet` tool used by the agent. |
| `llm/prompt/` | **System Prompts**. Logic for constructing LLM context. |
| `task/` | **Task Engine**. Base classes (`Task`, `CmdTask`) and runners. |
| `runner/` | **Entry Points**. CLI (`cli.py`) and Web Server (`web.py`). |

### 2.2. Configuration
- **Access:** Import `from zrb.config.config import CFG`.
- **Definition:** `src/zrb/config/config.py`.
- **Convention:** All global settings (URLs, API keys, defaults) MUST go here.

## 3. Development Conventions

### 3.1. Modifying Built-in Tasks (`src/zrb/builtin/`)
- These files define what happens when a **USER** runs `zrb <cmd>` in their terminal.
- **Goal:** Automate workflows (deploy, test, start services).
- **Context:** Tasks run with a `ctx` object containing `input`, `env`, and `print`.

### 3.2. Modifying LLM Tools (`src/zrb/llm/tool/`)
- These files define functions the **AGENT** (you) can call (e.g., `search_internet`, `read_file`).
- **Goal:** Give the agent capabilities to interact with the world.
- **Return Values:** Tools must return strings or JSON-serializable dicts.
- **Error Handling:** Catch expected errors (like connection refused) and return helpful, actionable error messages.
- **UX:** Use `[SYSTEM SUGGESTION]: ...` in error messages to guide the user (e.g., if a service is down, suggest the Zrb task to start it).

### 3.3. Modifying Core Logic
- **Safety:** Use `zrb.util` for common file/string operations.
- **Output:** Use `ctx.print` (in tasks) or standard logging.

## 4. Key Patterns
- **White-Labeling:** Use `CFG.ROOT_GROUP_NAME` instead of hardcoding "zrb" in strings displayed to users.
- **Lazy Loading:** Tasks and tools are often loaded lazily to speed up CLI startup.
- **Singletons:** Managers (Skill, Note) are module-level singletons.
