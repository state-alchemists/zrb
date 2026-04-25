# Zrb Agent Guide

## Project Overview
Zrb (Zaruba) is a Python-based task automation framework (v2.x). It supports task definition in pure Python, dependency-based execution (DAG), CLI and web UI runners, and built-in LLM/AI agent integration. Core logic is in `src/zrb/`.

## Development Setup
```bash
source .venv/bin/activate && poetry lock && poetry install
```

## Project Structure

### Core Framework
| Directory | Purpose |
|-----------|---------|
| `src/zrb/builtin/` | Pre-packaged user-executable tasks (`zrb <group> <task>`) |
| `src/zrb/config/` | Global settings via `CFG` singleton — class composed of mixins under `_mixins/` (foundation, web, llm_core, llm_ui, llm_limits, llm_content, llm_prompt, llm_search, rag, internet_search, hooks, task_runtime). `CFG.FOO` access stays flat. |
| `src/zrb/task/` | Task engine: `BaseTask`, `Task`, `CmdTask`, `LLMTask`, `Scheduler`, etc. |
| `src/zrb/runner/` | CLI (`Cli` class) and Web UI (`FastAPI` app) entry points |
| `src/zrb/group/` | CLI command group definitions (hierarchical task organization) |
| `src/zrb/input/` | Input parameter types: `StrInput`, `IntInput`, `BoolInput`, `OptionInput`, etc. |
| `src/zrb/env/` | Environment variable types: `Env`, `EnvMap`, `EnvFile` |
| `src/zrb/context/` | Per-task `Context` and shared `SharedContext` (inputs, envs, xcom) |
| `src/zrb/session/` | `Session` tracks execution state, task status, concurrent coroutines |
| `src/zrb/xcom/` | `Xcom` deque-based inter-task messaging (push/pop/peek) |
| `src/zrb/callback/` | Task lifecycle event callbacks |
| `src/zrb/attr/` | Attribute descriptors (StrAttr, IntAttr, BoolAttr, etc.) for deferred evaluation |
| `src/zrb/dot_dict/` | `DotDict` – dot-notation dict used for `ctx.input.*` and `ctx.env.*` |
| `src/zrb/cmd/` | Command rendering utilities for `CmdTask` |
| `src/zrb/content_transformer/` | Content transformation helpers (templating, string transforms) |
| `src/zrb/session_state_log/` | Session state data structures |
| `src/zrb/session_state_logger/` | Persistent session logging |
| `src/zrb/task_status/` | Task status tracking (PENDING, STARTED, READY, DONE, FAILED, etc.) |
| `src/zrb/util/` | General utility functions (git, file, string, async helpers) |
| `src/zrb/llm_plugin/` | Plugin discovery/loading for LLM agent extensions |

### LLM Integration (`src/zrb/llm/`)
| Directory | Purpose |
|-----------|---------|
| `llm/agent/` | `SubAgentManager` – multi-agent orchestration, tool registry |
| `llm/app/` | LLM application-level integration helpers |
| `llm/approval/` | Tool call approval protocols (`AnyToolConfirmation`, `ApprovalChannel`) |
| `llm/chat/` | `LLMChatTask` – interactive terminal chat sessions |
| `llm/config/` | `LLMConfig` (model selection, rate limiting) and `LLMLimiter` (token budgets) |
| `llm/custom_command/` | Custom CLI command integration for LLM tasks |
| `llm/history_manager/` | `FileHistoryManager` – persist and load conversation history |
| `llm/hook/` | `HookManager`, `HookContext` – Claude Code–compatible lifecycle hooks. Split: `manager.py` (registration + execution + executor factories), `_loader_mixin.py` (filesystem & format parsing), `matcher.py` (matcher operators + `evaluate_matchers`). |
| `llm/lsp/` | Language Server Protocol support for LLM tools |
| `llm/prompt/` | System prompts, mandates, context journal; `PromptManager` composes sections; configurable tool guidance via `add_tool_guidance()` |
| `llm/skill/` | `SkillManager` – reusable agent capabilities, dynamic activation |
| `llm/summarizer/` | Context compression and history summarization for long conversations |
| `llm/task/` | `LLMTask`, `LLMChatTask` – pydantic-ai–based tasks. `LLMChatTask` is split into `llm_chat_task.py` (init + `_exec_action` + `_create_llm_task_core`), `_chat_builder_mixin.py` (`add_*`/`set_*`/`append_*` API), `_chat_runner_mixin.py` (`_run_interactive_session` / `_run_non_interactive_session`). |
| `llm/tool/` | Agent-callable tools: `bash`, `file`, `code`, `web`, `rag`, `delegate`, `plan`, `mcp`, `skill`, `worktree`, `zrb_task`, `search/` |
| `llm/tool_call/` | Tool call data structures and result handling |
| `llm/ui/` | `UIProtocol` and terminal UI for streaming responses and tool approval. `BaseUI` is split into `base_ui.py` (lifecycle, AI streaming, tool confirmation) and `_commands_mixin.py` (slash-command handlers + `_run_shell_command` + `_stream_btw_response` + `_get_help_text`). |
| `llm/util/` | Internal LLM utilities |

### Test Locations
| Directory | Purpose |
|-----------|---------|
| `test/` | Tests mirroring `src/` hierarchy |
| `llm-challenges/` | Agent framework evaluation (contains `runner.py`) |

## Key Task Types

| Task Class | Import | Purpose |
|-----------|--------|---------|
| `Task` | `zrb.task.task` | Pure Python action (async or sync function) |
| `CmdTask` | `zrb.task.cmd_task` | Shell command execution (local or SSH remote) |
| `LLMTask` | `zrb.llm.task.llm_task` | Pydantic-AI agent with tools, skills, hooks |
| `HttpCheck` | `zrb.task.http_check` | HTTP readiness check |
| `TcpCheck` | `zrb.task.tcp_check` | TCP port readiness check |
| `Scheduler` | `zrb.task.scheduler` | Cron-style trigger (extends `BaseTrigger`) |
| `Scaffolder` | `zrb.task.scaffolder` | Jinja2 file templating / project scaffolding |
| `RsyncTask` | `zrb.task.rsync_task` | File sync / deploy via rsync |

## LLM Prompt System

`PromptManager` (`src/zrb/llm/prompt/manager.py`) assembles the system prompt from ordered sections (persona → git mandate → system context → mandate → tool guidance → journal → project context → skills → user prompts). Each section can be toggled via `include_*` flags or the corresponding `CFG.LLM_INCLUDE_*` env var.

### System Context Auto-Injections (`src/zrb/llm/prompt/system_context.py`)

The system context middleware runs once per prompt build and does three things beyond environment facts:

1. **Session wiring** — reads `ctx.input.session` and calls `set_current_tool_session()` (`src/zrb/llm/tool/ambient_state.py`). This sets a `ContextVar` that all four todo tools (`WriteTodos`, `GetTodos`, `UpdateTodo`, `ClearTodos`) read when called without an explicit `session=` argument, ensuring they always operate on the correct conversation session.

2. **Active worktree** — if `EnterWorktree` was called, its path is shown as `- Active worktree: <path>` in every subsequent system prompt, reminding the LLM to pass it as `cwd` to `Bash`. Cleared automatically when `ExitWorktree` is called. Read via `get_active_worktree()` from `src/zrb/llm/tool/ambient_state.py`.

3. **Pending todos** — if the current session has `pending` or `in_progress` todos, they are rendered into the system context so the LLM sees them at the start of every turn without needing to call `GetTodos` first. Completed and cancelled items are omitted.

### Ambient State (`ContextVar`s)

Zrb propagates seven ambient-state values via `contextvars.ContextVar`. The full list — with their typed wrappers — is re-exported from `src/zrb/contextvars.py` (the discoverability index). The vars themselves stay in their owning module:

| Var | Owner | Wrapper |
|-----|-------|---------|
| `current_ctx` | `src/zrb/context/any_context.py` | `get_current_ctx()` |
| `current_ui` | `src/zrb/llm/agent/run_agent.py` | `get_current_ui()` from `src/zrb/llm/agent/runtime_state.py` |
| `current_tool_confirmation` | `src/zrb/llm/agent/run_agent.py` | `get_current_tool_confirmation()` |
| `current_yolo` | `src/zrb/llm/agent/run_agent.py` | `get_current_yolo()` |
| `current_approval_channel` | `src/zrb/llm/approval/approval_channel.py` | `get_current_approval_channel()` |
| `active_worktree` | `src/zrb/llm/tool/worktree.py` | `get_active_worktree()` / `set_active_worktree()` from `src/zrb/llm/tool/ambient_state.py` |
| `_current_session` | `src/zrb/llm/tool/plan.py` | `get_current_tool_session()` / `set_current_tool_session()` |

When you only need to **read** ambient state, prefer the wrapper. When you need to scope a value for the duration of a block (`token = var.set(...)` then `var.reset(token)`), use the underlying `ContextVar` directly — see `run_agent.py` for the canonical pattern.

### Worktree Storage

Git worktrees are created at `{git_root}/.zrb/worktree/{branch_name}`. This directory is listed in `.gitignore`.

### Configuring Tool Guidance

Tool guidance is fully explicit — there is no static catalogue. Register entries via `PromptManager`:

```python
llm_chat.prompt_manager.add_tool_guidance(
    group="My Tools",
    name="MyTool",
    use_when="Doing X when Y",
    key_rule="Always pass --flag; never call without context.",  # optional
)
```

`add_tool_group(name=...)` is called automatically by `add_tool_guidance` when the group does not yet exist. Calling it explicitly is only needed to pre-declare an empty group or control order.

`LLMChatTask._exec_action` automatically sets `prompt_manager.tool_names` from the resolved tool list at runtime, so guidance for unregistered tools is suppressed. For factory-created tools (whose Python function names differ from their LLM-visible names), add an `add_tool_guidance()` entry to ensure their guidance is included.

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

**Coverage Exclusions (`.coveragerc`):**
The following files are excluded from coverage reporting:
- **Protocol/Interface files** (`any_*.py`): Base protocols and interfaces that define contracts but have no implementation
- **Entry points** (`__main__.py`): Script entry points that are tested via integration tests
- **Package init files** (`__init__.py`): Re-exports only, tested through public API usage
- **User init file** (`zrb_init.py`): User-defined initialization, not library code

Do NOT attempt to test these excluded files directly. They are intentionally omitted from coverage metrics.
