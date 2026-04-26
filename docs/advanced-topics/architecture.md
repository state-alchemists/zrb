🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Architecture, Philosophy, & Conventions

# Zrb Architecture, Philosophy, & Conventions

This document is aimed at maintainers, contributors, and curious power users who want to understand the *why* and *how* behind Zrb's codebase. Zrb is a complex, asynchronous task execution framework masquerading as a simple automation tool. Navigating its internals requires understanding its core design philosophies.

---

## 1. Core Philosophy

### Python as the Ultimate DSL
Zrb explicitly rejects YAML, JSON, or custom Domain Specific Languages (DSLs) for defining automation pipelines. 
* **Why:** YAML pipelines often reinvent programming constructs poorly (e.g., awkward syntax for loops, conditionals, or string interpolation). By using pure Python, users get type safety, linting, code completion, and the entire PyPI ecosystem out of the box.
* **Implication:** The framework must be expressive and ergonomic. We use `__rshift__` (`>>`) and `__lshift__` (`<<`) operator overloading to make task dependency chaining visually intuitive.

### Interfaces Everywhere (The `Any*` Pattern)
If you browse `src/zrb`, you will immediately notice files like `any_task.py`, `any_session.py`, and `any_context.py`. Zrb relies heavily on Abstract Base Classes (ABCs).
* **Why:** Total decoupling. It allows the core execution engine to run without caring about the concrete implementation of a task. It makes mocking in tests straightforward and allows power users to inject entirely custom task logic.
* **Convention:** Always program against the `Any` interface, not the concrete implementation (e.g., expect `AnySession` in method signatures, not `Session`).

### Asynchronous First
Zrb is designed from the ground up on Python's `asyncio`.
* **Why:** Automation often involves waiting—waiting for a database to boot, waiting for a web server to respond, or waiting for an LLM to stream a response. `asyncio` allows massive concurrency without the overhead of threads.
* **Implication:** Synchronous entry points (like `task.run()`) merely spin up an asyncio event loop to execute the asynchronous core (`async_run()`).

---

## 2. Architectural Decisions

### The Task Execution Lifecycle
Execution is highly abstracted and deeply nested to handle DAG (Directed Acyclic Graph) resolution, concurrency, and readiness checks. The flow generally follows:
1. `run()` (or `async_run()`): Initializes the `Session` and `SharedContext`.
2. `exec_root_tasks()`: Identifies tasks with no upstreams and starts their chains.
3. `exec_chain()`: Concurrently runs a task and, upon success, its `successors`.
4. `execute_action_until_ready()`: Evaluates `execute_condition` and runs `readiness_checks` concurrently before executing the main action.
5. `execute_action_with_retry()`: Contains the core try/catch, retry loop, XCom pushing, and triggers `fallbacks` on failure.

### Implicit State via `ContextVars`
Instead of threading `session`, `logger`, or `env` through every single function signature, Zrb relies on `contextvars` (specifically `current_ctx`).
* **Why:** In deeply nested task execution, passing context variables explicitly clutters the API and developer experience.
* **How it works:** When a task begins execution, it binds its specific `AnyContext` to the `current_ctx`. `asyncio` natively propagates context variables to child coroutines. Functions deeper in the stack can retrieve the active context via `get_current_ctx()`.

### Ergonomic Data Access (`DotDict`)
Zrb uses a custom dictionary subclass called `DotDict` for `ctx.env`, `ctx.input`, and `ctx.xcom`.
* **Why:** `ctx.env.MY_VAR` is more readable and Pythonic to write than `ctx.env.get("MY_VAR")` or `ctx.env["MY_VAR"]`. It bridges the gap between structured objects and dynamic dictionaries.

### Robust LLM Integration
Zrb treats Large Language Models not just as APIs, but as sophisticated, recursive agents using `pydantic-ai`.
* **Hooks and Tools:** Tools are passed as Python callables. Agents can recursively invoke sub-agents. 
* **Inherited Context:** LLM constraints (like `yolo` mode, active UI, or approval channels) are inherited dynamically from parent agents through `ContextVars` to ensure security policies bypass strict argument passing boundaries.

---

## 3. Coding Conventions

### Handling Asynchronous Cancellation
Tasks in Zrb can be cancelled (e.g., a user hits `Ctrl+C`, or a parent task fails).
* **Rule:** You must *always* catch `(asyncio.CancelledError, KeyboardInterrupt, GeneratorExit)` separately from standard exceptions.
* **Action:** Mark the task status as failed, perform necessary resource cleanup, and **re-raise** the cancellation error to ensure the event loop tears down gracefully.

```python
try:
    result = await my_async_op()
except (asyncio.CancelledError, KeyboardInterrupt, GeneratorExit):
    ctx.log_warning("Task cancelled")
    session.get_task_status(task).mark_as_failed()
    raise
except Exception as e:
    # Handle standard retryable/fallback errors
```

### Type Hinting & Circular Imports
Because Zrb is highly decoupled, objects often need to reference each other (e.g., `Task` needs `Session`, `Session` needs `Task`).
* **Rule:** Use `from typing import TYPE_CHECKING` extensively. Only import interfaces globally if absolutely necessary at runtime.
* **Action:** Use stringized type hints or `from __future__ import annotations` to prevent `ImportError`.

### Developer-Centric Error Tracking
When an exception occurs deep within `asyncio.gather`, standard tracebacks are often useless. 
* **Convention:** The `BaseTask` constructor captures the exact file and line number where the user defined the task (`self.__decl_file`, `self.__decl_line`) using the `inspect` module.
* **Usage:** When an action fails, this metadata is injected into the exception notes (`e.add_note()`). Always preserve this mechanism so the user knows *which of their defined tasks* caused the crash.

### F-String and Jinja Rendering
We defer execution of dynamic parameters. Many attributes accept `fstring` or strings containing `Jinja2` syntax. 
* **Convention:** Never trust a string property as static. Pass it through `ctx.render(task.property)` immediately before execution to ensure the most up-to-date Environment Variables or XCom data is populated.
