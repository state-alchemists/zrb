🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Maintainer Guide

# Maintainer Guide

This guide is for developers who contribute to or maintain the Zrb project itself. It outlines the project's architecture, conventions, and release process.

---

## Table of Contents

- [Publishing Zrb](#publishing-zrb)
- [Inspecting Import Performance](#inspecting-import-performance)
- [Profiling Zrb](#profiling-zrb)
- [Testing Strategies](#testing-strategies)
- [Evaluating the LLM Agent](#evaluating-and-improving-the-llm-agent)
- [Architecture & Philosophy](#architecture--philosophy)
- [Context Propagation Internals](#context-propagation-internals)
- [Quick Reference](#quick-reference)

---

## Publishing Zrb

To publish Zrb, you need a PyPI account and an API token.

### Prerequisites

| Platform | URL |
|----------|-----|
| PyPI | https://pypi.org/ |
| TestPyPI | https://test.pypi.org/ |

### Configuration

```bash
poetry config pypi-token.pypi <your-api-token>
```

### Publishing

```bash
source ./project.sh
docker login -U stalchmst
zrb publish all
```

---

## Inspecting Import Performance

To inspect import performance and decide if a module should be lazy-loaded:

```bash
pip install benchmark-imports
python -m benchmark_imports zrb
```

---

## Profiling Zrb

To diagnose performance issues, generate a profile and visualize it.

### Generate Profile

```bash
python -m cProfile -o .cprofile.prof -m zrb --help
```

### Visualization Options

| Tool | Output | Command |
|------|--------|---------|
| `snakeviz` | Interactive HTML | `pip install snakeviz && snakeviz .cprofile.prof` |
| `flameprof` | Flame graph SVG | `pip install flameprof && flameprof .cprofile.prof > flamegraph.svg` |

---

## Testing Strategies

The test suite uses `pytest` fixtures and `unittest.mock.patch` (as decorators or context managers) to isolate components and ensure correctness.

Refer to existing tests in the `test/` directory for examples.

---

## Evaluating and Improving the LLM Agent

To maintain and improve the quality of the Zrb LLM agent, the project uses a set of automated evaluation challenges located in the `llm-challenges/` directory.

> 💡 **See:** `llm-challenges/AGENTS.md` for full evaluation protocol instructions.

### Process Overview

| Step | Action |
|------|--------|
| 1. Execute | Run challenges for all model combinations |
| 2. Analyze | Review generated REPORT.md for failures |
| 3. Optimize | Refactor prompts or tools |
| 4. Verify | Re-run challenges to confirm improvements |

### Running Challenges

```bash
cd llm-challenges/

# Quick verification test
python runner.py --models openai:gpt-4o google-gla:gemini-1.5-pro --timeout 120 --verbose

# Full test suite
python runner.py --timeout 3600 --parallelism 12 --verbose --models <model-list>
```

### Analyzing Results

| Output | Location |
|--------|----------|
| Report | `llm-challenges/experiment/REPORT.md` |
| Results | `llm-challenges/experiment/results.json` |

### Optimization Targets

| Target | Location |
|--------|----------|
| Prompts | `src/zrb/llm/prompt/markdown/` |
| Tools | `src/zrb/llm/tool/` |

---

## Architecture & Philosophy

To understand Zrb's core design decisions (such as the strict use of `asyncio`, the `Any*` decoupled interface pattern, and the underlying data flow), please read the dedicated **[Architecture, Philosophy, & Conventions](./architecture.md)** document.

---

## Context Propagation Internals

Zrb uses Python's `contextvars.ContextVar` to thread execution state through async coroutines without explicit parameter passing. There are five `ContextVar` instances across the codebase, split into two layers.

### The Two Layers

**Layer 1 — Task execution** (`src/zrb/context/any_context.py:229`):

```python
current_ctx: ContextVar[AnyContext | None] = ContextVar("current_ctx", default=None)
```

Holds the active `Context` for the currently executing task. Set at the start of `execute_task_action()`, reset in its `finally` block.

**Layer 2 — LLM agent execution** (`src/zrb/llm/agent/run_agent.py`):

| Variable | Type | Purpose |
|---|---|---|
| `current_ui` | `UIProtocol \| None` | Active UI for output and user interaction |
| `current_tool_confirmation` | `AnyToolConfirmation` | Tool approval policy |
| `current_yolo` | `bool` | Auto-approve all tool calls |
| `current_approval_channel` | `ApprovalChannel \| None` | Remote approval handler |

All four are set at the start of `run_agent()` and reset in its `finally` block.

### The Scoping Pattern

Every `ContextVar` follows the same RAII-style pattern:

```python
token = current_ctx.set(ctx)
try:
    ...task body...
finally:
    current_ctx.reset(token)  # restores the previous value
```

The `reset(token)` call restores whatever value was in the variable before `set()` was called. This means nested calls (e.g. a sub-agent delegated from a parent agent) each get their own scope while still inheriting the parent's values at entry time.

### Inheritance Pattern

Agent context variables use a fallback pattern to enable parent→child inheritance:

```python
# run_agent.py — resolve effective value
effective_ui = ui_arg or current_ui.get()
effective_yolo = yolo or current_yolo.get()
```

If a child agent doesn't receive an explicit argument, it inherits from the context set by its parent. This allows YOLO mode, approval channels, and UI handles to flow naturally through nested agent calls.

### Why ContextVar (not Globals or Thread-locals)?

Zrb is fully asyncio-based. Thread-locals don't work with coroutines (multiple coroutines share a thread). A global dict keyed on task/session ID would work but adds lookup overhead and manual lifecycle management. `ContextVar` integrates directly with Python's asyncio scheduler:

- `asyncio.create_task()` automatically copies the current context to the new task (PEP 567).
- `asyncio.gather()` runs coroutines in-place, sharing the caller's context.
- Token-based `reset()` ensures correct cleanup even if exceptions occur.

### Known Inefficiency: `env` Dict Copy

Every time a `Context` object is created for a task (`context.py:25`), it copies the entire shared env dictionary:

```python
self._env = shared_ctx.env.copy()
```

This is O(n) in the number of env vars and happens once per task execution. For typical workloads (< 100 vars, dozens of tasks) it is not a bottleneck. If you are seeing memory pressure under large fan-out workloads (hundreds of concurrent tasks, large envs), this is the first place to look — a lazy/copy-on-write approach would eliminate redundant copies.

### Gotcha: `asyncio.create_task()` and Context Timing

At `execution.py:97`, a new asyncio task is created for action execution:

```python
action_coro = asyncio.create_task(run_async(execute_action_with_retry(task, session)))
```

Python copies the context at `create_task()` time. If the parent coroutine resets `current_ctx` before the new task is scheduled, the new task runs with the snapshot value from creation time — which may differ from the parent's current value. This is safe in practice because `execute_action_with_retry` re-establishes its own `current_ctx` scope, but it is worth keeping in mind if the execution model changes.

---

## Quick Reference

| Task | Command |
|------|---------|
| Publish | `zrb publish all` |
| Profile imports | `python -m benchmark_imports zrb` |
| Generate profile | `python -m cProfile -o .cprofile.prof -m zrb --help` |
| Visualize (snakeviz) | `snakeviz .cprofile.prof` |
| Visualize (flame) | `flameprof .cprofile.prof > flamegraph.svg` |
| Run LLM challenges | `python runner.py --models <list> --verbose` |

---