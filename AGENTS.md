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
| `llm/prompt/journal.py` | **Journal Prompt Component**. Directory-based journaling with auto-injected index file. |
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

### 3.4. Refactoring Guidelines
- **Structure:** Public functions (used by other modules) must be at the top of the file.
- **Function Size:** Functions should be short enough to fit on a single screen (concise logic).
- **Ordering:** Detailed helper functions should be located below the functions that call them (caller top, callee bottom).
- **Dependencies:** Organize imports cleanly at the top.

### 3.5. Journal System
- **Purpose:** Directory-based journaling for agents to maintain context across sessions.
- **Location:** `~/.zrb/llm-notes/` (configurable via `CFG.LLM_JOURNAL_DIR`)
- **Index File:** `index.md` (configurable via `CFG.LLM_JOURNAL_INDEX_FILE`) is auto-injected into system prompts.
- **Organization:** Create hierarchical structure by topic (e.g., `project-a/design.md`, `project-b/meeting-notes.md`)
- **Integration:** Only the index file is injected, not all journal files. Keep index concise with references.
- **Documentation:** Use AGENTS.md for technical documentation only. Use journal for non-technical notes, reflections, and project context.

## 4. Key Patterns
- **White-Labeling:** Use `CFG.ROOT_GROUP_NAME` instead of hardcoding "zrb" in strings displayed to users.
- **Lazy Loading:** Tasks and tools are often loaded lazily to speed up CLI startup.
- **Singletons:** Managers (Skill, Hook) are module-level singletons.
- **Journal System:** Directory-based journaling with auto-injected index for agent context.

## 5. Testing
- **Test Command:** Run `source .venv/bin/activate && ./zrb-test.sh <parameter>` where `<parameter>` can be:
  - Empty: Runs all tests
  - Test file path: Runs specific test file (e.g., `test/llm/prompt/test_journal.py`)
  - Test directory: Runs all tests in directory (e.g., `test/llm/prompt/`)
  - Test function: Runs specific test (e.g., `test/llm/prompt/test_journal.py::test_journal_prompt_with_empty_journal`)
- **Coverage Goal:** Maintain ≥75% overall code coverage.
- **Test Structure:** Tests are organized in `test/` mirroring `src/` structure.
- **Test Conventions:** Use pytest fixtures, mocks for external dependencies, and follow AAA pattern (Arrange-Act-Assert).
