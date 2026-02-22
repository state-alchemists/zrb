# Zrb Agent Guide

## 1. What the Project Is
Zrb is a Python-based task automation tool. The core logic, built-in tasks, and LLM integrations are defined in the `src/zrb/` directory.

## 2. Development Setup
To set up the project, initialize the virtual environment, install dependencies (via poetry), and configure your shell, run:
```bash
source project.sh
```

## 3. Where to Find Files

### Core Framework
- **`src/zrb/builtin/`**: User-executable task definitions (`zrb <group> <task>`).
- **`src/zrb/config/`**: Global settings via `CFG` (URLs, API keys, defaults).
- **`src/zrb/task/`**: Core task engine, base classes, and runners.
- **`src/zrb/runner/`**: CLI and Web Server entry points.
- **`src/zrb/group/`**: Command group definitions.
- **`src/zrb/input/`**: Input parameter definitions for CLI execution.
- **`src/zrb/util/`**: General utility functions.

### LLM Integration (`src/zrb/llm/`)
- **`src/zrb/llm/agent/`**: Agent orchestrators and execution logic.
- **`src/zrb/llm/prompt/`**: Logic for LLM system prompts, mandates, and context.
- **`src/zrb/llm/skill/`**: Agent skills and behavioral logic.
- **`src/zrb/llm/tool/`**: Agent-callable Python functions (e.g., `search_internet`).

### Testing & Evaluation
- **`test/`**: Contains tests mirroring the `src/` hierarchy.
- **`llm-challenges/`**: Contains challenges and the `runner.py` script to test and evaluate the agent framework capabilities.

## 4. Development Conventions
- **Public API Focus**: Only test public functions/methods. Avoid importing or testing private members (prefixed with `_`).
- **Code Style**: Follow existing project conventions (formatting, naming, typing).
- **Modularity**: Functions should be concise (ideally fit on one screen).
- **Readability**: Place detailed helper functions below their callers.
- **Error Handling (Tools)**: Return actionable error messages, including `[SYSTEM SUGGESTION]` for user guidance.

## 5. Testing Guidelines
- **Command**: `source project.sh && ./zrb-test.sh [parameter]`
- **Parameters**:
  - `(empty)`: Runs all tests.
  - `<file_path>`: Runs tests in a specific file (e.g., `test/llm/prompt/test_journal.py`).
  - `<directory_path>`: Runs tests in a directory (e.g., `test/llm/prompt/`).
  - `<test_function>`: Runs a specific test (e.g., `test/llm/prompt/test_journal.py::test_journal_prompt_with_empty_journal`).
- **Structure**: Tests are organized in `test/` mirroring the `src/` hierarchy.
- **Coverage**: Aim for ≥75% overall code coverage.
- **Principles**: Use `pytest` fixtures, mocks for external dependencies, and the Arrange-Act-Assert (AAA) pattern.
