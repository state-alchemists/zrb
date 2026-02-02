# AGENTS.md - ZRB Project Agent Configuration

> This file contains agent configurations and coding guidelines for the ZRB project.

---

## 📋 Overview

**ZRB** is a Python-based task runner and automation framework with built-in LLM integration.

- **Language**: Python 3.11+
- **Framework**: FastAPI (for web UI), Pydantic-AI (for LLM)
- **Package Manager**: Poetry
- **License**: AGPL-3.0-or-later

---

## 🤖 Specialized Agents

This project includes specialized agent configurations for various tasks:

| Agent | Purpose | Location |
|-------|---------|----------|
| **Documentation** | Generate and maintain documentation | [`agents/documentation/AGENTS.md`](agents/documentation/AGENTS.md) |
| **Planning** | Project planning and task breakdown | [`agents/planning/AGENTS.md`](agents/planning/AGENTS.md) |
| **Testing** | Write and analyze tests | [`agents/testing/AGENTS.md`](agents/testing/AGENTS.md) |
| **Refactoring** | Code modernization and refactoring | [`agents/refactoring/AGENTS.md`](agents/refactoring/AGENTS.md) |
| **Research** | Academic research and journal writing | [`agents/research/AGENTS.md`](agents/research/AGENTS.md) |

See [`agents/AGENTS.md`](agents/AGENTS.md) for the complete agent index.

---

## 📊 Research Paper

This project includes a comprehensive research paper on LLM evaluation:

**Paper:** "Comprehensive Evaluation of Large Language Models on Software Engineering Tasks"  
**Location:** [`llm-challenges/experiment/paper/`](llm-challenges/experiment/paper/)

### Paper Highlights
- **13 LLM models** evaluated across **5 software engineering tasks**
- **Key Finding:** Tool usage does not correlate with success (r=0.077)
- **Data:** 55 experiment runs with automated verification
- **Status:** Full draft complete (8-10 pages, IEEE format)

### Paper Structure
```
llm-challenges/experiment/
├── paper/               # LaTeX source files
├── analysis/            # Data processing scripts
├── figures/             # Publication-ready figures
└── docs/                # Research questions and planning
```

---

## 🏗️ Project Structure

```
src/zrb/
├── __init__.py           # Main exports
├── __main__.py           # CLI entry point
├── attr/                 # Attribute types (fstring, etc.)
├── builtin/              # Built-in tasks (git, http, project scaffolding, etc.)
├── callback/             # Callback system
├── cmd/                  # Command execution utilities
├── config/               # Configuration management
├── content_transformer/  # Content transformation
├── context/              # Task execution context
├── dot_dict/             # Dot notation dictionary
├── env/                  # Environment variable handling
├── group/                # Task groups
├── input/                # Input types (str, int, bool, etc.)
├── llm/                  # LLM integration (agent, tools, prompts)
├── runner/               # CLI and Web runners
├── session/              # Session management
├── task/                 # Task implementations
├── util/                 # Utilities
└── xcom/                 # Cross-task communication
```

---

## 🎯 Core Concepts

### Task Types

- **Task**: Basic Python function task
- **CmdTask**: Shell command execution
- **LLMTask**: AI-powered task with LLM
- **LLMChatTask**: Interactive LLM chat
- **HttpCheck**: HTTP endpoint health check
- **TcpCheck**: TCP port health check
- **RsyncTask**: File synchronization
- **Scaffolder**: Code generation from templates
- **Scheduler**: Cron-like scheduled tasks

### Key Components

1. **Context (`AnyContext`)**: Execution context with inputs, env, xcom
2. **XCom**: Cross-task data exchange
3. **Inputs**: Typed inputs (StrInput, IntInput, BoolInput, etc.)
4. **Groups**: Organize tasks hierarchically
5. **Dependencies**: `upstream`, `successor`, `fallback` relationships

---

## 🧪 Development Guidelines

### Code Style

- **Formatter**: Black (line length 88)
- **Import Sorter**: isort
- **Linter**: flake8
- Use type hints everywhere
- Use `from __future__ import annotations` for forward references

### Naming Conventions

- **Classes**: PascalCase (e.g., `LLMTask`, `CmdTask`)
- **Functions/Methods**: snake_case (e.g., `run_agent`, `get_attr`)
- **Constants**: UPPER_CASE (e.g., `CFG`, `LLM_CONFIG`)
- **Private**: Prefix with underscore (e.g., `_exec_action`, `_get_model`)

### Async/Await Pattern

- All task actions are async: `async def _exec_action(self, ctx)`
- Use `await asyncio.sleep(0)` for cooperative multitasking
- Wrap sync tools with safe wrappers for error handling

### Error Handling

```python
try:
    result = await some_async_operation()
except Exception as e:
    return f"Error executing {func.__name__}: {e}"
```

---

## 🤖 Available Tools

### LLM Tools (src/zrb/llm/tool/)

- `analyze_code`: Analyze code structure
- `write_file`: Write content to files
- `bash`: Execute shell commands
- `mcp`: Model Context Protocol integration
- `rag`: Retrieval Augmented Generation
- `search/`: Web search (brave, serpapi, searxng)
- `sub_agent`: Spawn sub-agents
- `zrb_task`: Invoke ZRB tasks

### File Operations

- `load_file`: Load Python files dynamically
- `load_module`: Load modules

---

## 📚 Task Definition Example

```python
from zrb import cli, LLMTask, CmdTask, StrInput, Group

# Create a group
my_group = cli.add_group(Group(name="myapp", description="My App Tasks"))

# Define a task
task = my_group.add_task(
    LLMTask(
        name="generate-docs",
        description="Generate documentation",
        input=[
            StrInput(name="target_dir", default="./"),
        ],
        message="Generate README.md for {ctx.input.target_dir}",
        tools=[analyze_code, write_file],
    )
)
```

---

## 🔧 Build & Test

```bash
# Install dependencies
poetry install

# Run tests
pytest

# Format code
black src/
isort src/

# Lint
flake8 src/

# Run ZRB
python -m zrb --help
```

---

## 📖 Documentation

Full documentation available in `docs/` directory:
- `docs/core-concepts/`: Core concepts and architecture
- `docs/installation-and-configuration/`: Setup guides
- `docs/advanced-topics/`: Advanced usage

---

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and notable changes.

---

*Last updated: 2026-02-02*
