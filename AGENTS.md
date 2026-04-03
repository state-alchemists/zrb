# Zrb Agent Guide

## Project Overview
Zrb is a Python-based task automation tool. Core logic, built-in tasks, and LLM integrations are in `src/zrb/`.

## Development Setup
```bash
source .venv/bin/activate && poetry lock && poetry install
```

## Project Structure

### Core Framework
| Directory | Purpose |
|-----------|---------|
| `src/zrb/builtin/` | User-executable task definitions (`zrb <group> <task>`) |
| `src/zrb/config/` | Global settings via `CFG` (URLs, API keys, defaults) |
| `src/zrb/task/` | Core task engine, base classes, runners |
| `src/zrb/runner/` | CLI and Web Server entry points |
| `src/zrb/group/` | Command group definitions |
| `src/zrb/input/` | Input parameter definitions for CLI execution |
| `src/zrb/util/` | General utility functions |

### LLM Integration
| Directory | Purpose |
|-----------|---------|
| `src/zrb/llm/agent/` | Agent orchestrators and execution logic |
| `src/zrb/llm/prompt/` | LLM system prompts, mandates, context |
| `src/zrb/llm/skill/` | Agent skills and behavioral logic |
| `src/zrb/llm/tool/` | Agent-callable Python functions (e.g., `search_internet`) |

### Test Locations
| Directory | Purpose |
|-----------|---------|
| `test/` | Tests mirroring `src/` hierarchy |
| `llm-challenges/` | Agent framework evaluation (contains `runner.py`) |

## Development Conventions

### Code Style
- Follow existing project conventions (formatting, naming, typing)
- **Modularity**: Functions should be concise (~30-50 lines)
- **Readability**: Place helper functions below their callers
- **Error Handling**: For LLM tool errors, include `[SYSTEM SUGGESTION]` prefix with actionable guidance

### Test Guidelines

**Run Tests:**
```bash
source .venv/bin/activate && ./zrb-test.sh [parameter]
```

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| (empty) | Run all tests | — |
| `<file_path>` | Run tests in a file | `test/llm/prompt/test_journal.py` |
| `<directory_path>` | Run tests in a directory | `test/llm/prompt/` |
| `<test_function>` | Run a specific test | `test/llm/prompt/test_journal.py::test_journal_prompt_with_empty_journal` |

**Principles:**
- **Coverage**: Aim for ≥80%
- **Public API Only**: 
  - ❌ **NEVER** access or test private members (anything with `_` prefix)
  - This includes: `._private_attr`, `._private_method()`, accessing `._internal_state`
  - Private members are implementation details - tests should verify behavior through public interfaces
  - If internal behavior is hard to test publicly, refactor the class to expose a public hook or property
  - Example violations to avoid:
    ```python
    # ❌ WRONG: Testing private attribute
    assert obj._internal_state == "expected"
    
    # ❌ WRONG: Testing private method
    obj._process_data()
    
    # ✅ CORRECT: Test through public API
    obj.do_something()  # Internally calls _process_data()
    assert obj.get_state() == "expected"  # Public property/method
    ```
- Use `pytest` fixtures and mocks for external dependencies
- Follow Arrange-Act-Assert (AAA) pattern

**Test File Conventions:**
- ❌ No suffixes: `_advanced.py`, `_coverage.py`, `_extra.py`, `_comprehensive.py`
- ✅ Single source of truth: Update main test file (e.g., `test_manager.py`)
- ✅ Split large files (>500 lines) by **feature group** (e.g., `test_manager_lifecycle.py`, `test_manager_search.py`), NOT by depth or coverage level
