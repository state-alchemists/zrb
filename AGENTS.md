# Zrb Agent Guide

## 1. Project Conventions & Arrangement

### 1.1. Core Library (`src/zrb/`)
- **Purpose**: Python-based task automation tool.
- **Layout**: Files in `src/zrb/` define the core logic, built-in tasks, and LLM integrations.
- **Key Directories**:
  - `builtin/`: User-executable task definitions (`zrb <group> <task>`).
  - `config/`: Global settings via `CFG` (URLs, API keys, defaults).
  - `llm/tool/`: Agent-callable Python functions (e.g., `search_internet`).
  - `llm/prompt/`: Logic for LLM system prompts and context.
  - `task/`: Core task engine, base classes, and runners.
  - `runner/`: CLI and Web Server entry points.

### 1.2. Development Standards
- **Public API Focus**: Only test public functions/methods. Avoid importing or testing private members (prefixed with `_`).
- **Code Style**: Follow existing project conventions (formatting, naming, typing).
- **Modularity**: Functions should be concise (ideally fit on one screen).
- **Readability**: Place detailed helper functions below their callers.
- **Error Handling (Tools)**: Return actionable error messages, including `[SYSTEM SUGGESTION]` for user guidance.

## 2. Testing Guidelines

### 2.1. Running Tests
- **Command**: `source .venv/bin/activate && ./zrb-test.sh [parameter]`
- **Parameters**:
  - (empty): Runs all tests.
  - `<file_path>`: Runs tests in a specific file (e.g., `test/llm/prompt/test_journal.py`).
  - `<directory_path>`: Runs tests in a directory (e.g., `test/llm/prompt/`).
  - `<test_function>`: Runs a specific test (e.g., `test/llm/prompt/test_journal.py::test_journal_prompt_with_empty_journal`).
- **Structure**: Tests are organized in `test/` mirroring `src/` hierarchy.
- **Coverage**: Aim for ≥75% overall code coverage.

### 2.2. Test Writing
- **Principles**: Use `pytest` fixtures, mocks for external dependencies, and the Arrange-Act-Assert (AAA) pattern.

## 3. Other Important Aspects

### 3.1. Journal System
- **Purpose**: Directory-based journaling for agents to maintain context across sessions.
- **Location**: `~/.zrb/llm-notes/` (configurable).
- **Usage**: Only `index.md` (configurable) is auto-injected into system prompts. Keep index concise with references.
- **Distinction**: `AGENTS.md` for technical documentation; journal for non-technical notes, reflections, and project context.

### 3.2. LLM Summarization System (Agent Specific)
- **Purpose**: Manages LLM conversational history to prevent token limits.
- **Logic**:
  - `message_threshold`: Triggers summarization of individual large messages (e.g., tool returns).
  - `conversational_threshold`: The hard limit for conversational history. Content exceeding this is aggressively truncated.
- **Safety**: `find_best_effort_split` ensures tool call/return pairs are not broken during truncation/summarization.
- **Efficiency**: `summarize_long_text` uses recursive chunking with a recursion depth guard.
- **Context Preservation**: Extracts `<state_snapshot>` tags from summaries to maintain structured state.
### 3.3. LLM Message Safety
- **Core Principle**: Zrb enforces strict message structure rules to satisfy LLM API requirements (especially Anthropic/OpenAI via Pydantic AI).
- **Role Alternation**:
  - **Rule**: Messages must strictly alternate between `user` and `model` roles.
  - **Enforcement**: `zrb.llm.message.ensure_alternating_roles` merges consecutive same-role messages.
  - **Exceptions**: Tool calls and returns are treated as part of the `model` or `user` flow but must be paired correctly.
- **Tool Integrity**:
  - **Rule**: Every `ToolCall` must have a corresponding `ToolReturn`. They must never be separated by history splitting or summarization.
  - **Validation**: `zrb.llm.message.validate_tool_pair_integrity` checks for orphaned calls or returns.
  - **Splitting Strategy**: History splitters use `get_tool_pairs` to ensure splits happen *outside* of tool call/return blocks.
