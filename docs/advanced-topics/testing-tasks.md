🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Testing Zrb Tasks

# Testing Zrb Tasks

Zrb tasks are Python code, so they can be tested with standard Python testing tools like `pytest`. This guide covers patterns for testing both `Task`/`@make_task` functions and `CmdTask` shell commands.

---

## Table of Contents

- [Test File Organization](#test-file-organization)
- [Testing `@make_task` Functions](#testing-make_task-functions)
- [Testing `CmdTask` Commands](#testing-cmdtask-commands)
- [Testing with Context](#testing-with-context)
- [Testing Dependencies & Pipelines](#testing-dependencies--pipelines)
- [Running Tests](#running-tests)

---

## Test File Organization

Tests live in the `test/` directory, mirroring the `src/` structure:

```
test/
├── conftest.py              # Shared fixtures
├── builtin/
│   └── test_git.py
├── llm/
│   └── prompt/
│       └── test_manager.py
└── task/
    └── test_base_task.py
```

### Basic Fixture (`conftest.py`)

```python
import pytest
from zrb import Task, CmdTask, Group, cli

@pytest.fixture
def clean_cli():
    """Provide a fresh CLI group for each test."""
    return Group(name="test")
```

---

## Testing `@make_task` Functions

### Approach 1: Call the Function Directly

The simplest approach — your task action is just a Python function. Import and call it:

```python
from zrb.context.any_context import AnyContext

# my_tasks.py
from zrb import make_task, cli

@make_task(name="add", group=cli)
def add_task(ctx):
    a = ctx.input.a
    b = ctx.input.b
    result = a + b
    ctx.print(f"Result: {result}")
    return result
```

```python
# test_my_tasks.py
from unittest.mock import MagicMock
from my_tasks import add_task

async def test_add_task():
    # Create a mock context
    ctx = MagicMock()
    ctx.input.a = 3
    ctx.input.b = 4
    
    # Import and call the underlying function directly
    from my_tasks import add_task
    result = await add_task._exec_action(ctx)
    
    assert result == 7
```

### Approach 2: Mock the Context

For more control, use the test utilities from `zrb.context`:

```python
from unittest.mock import MagicMock
from zrb.context.any_context import AnyContext

async def test_complex_logic():
    ctx = MagicMock(spec=AnyContext)
    ctx.input.name = "test"
    ctx.input.count = 5
    ctx.env.MODE = "testing"
    
    result = await my_task._exec_action(ctx)
    assert result is not None
```

---

## Testing `CmdTask` Commands

For `CmdTask`, you can run the task programmatically and verify the command execution:

```python
import pytest
from unittest.mock import MagicMock
from zrb import CmdTask, Group
from zrb.context.any_context import AnyContext

@pytest.mark.asyncio
async def test_cmd_task_execution():
    group = Group(name="test")
    task = group.add_task(CmdTask(
        name="echo-test",
        cmd="echo 'Hello, Test!'",
    ))
    
    # Build a minimal mock context to drive the task
    ctx = MagicMock(spec=AnyContext)
    
    # Execute the task
    result = await task._exec_action(ctx)
    assert result is not None
```

---

## Testing with Context

For more realistic tests that exercise the full session/context wiring, create a minimal `Context`:

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from zrb.context.any_context import AnyContext
from zrb.dot_dict.dot_dict import DotDict
from zrb.session.session import Session

def create_test_context(task, inputs=None, envs=None):
    """Create a minimal test context."""
    session = MagicMock(spec=Session)
    session.get_task_status.return_value = MagicMock()
    
    ctx = MagicMock(spec=AnyContext)
    ctx.task = task
    ctx.session = session
    ctx.session_id = "test-session"
    ctx.task_name = task.name
    ctx.attempt = 1
    
    # Inputs
    ctx.input = DotDict(inputs or {})
    
    # Environment
    ctx.env = DotDict(envs or {})
    
    # XCom
    from collections import deque
    xcom_dict = {}
    ctx.xcom = MagicMock()
    ctx.xcom.__getitem__.side_effect = lambda name: xcom_dict.setdefault(name, deque())
    
    # Print / log mocks
    ctx.print = MagicMock()
    ctx.log_info = MagicMock()
    ctx.log_error = MagicMock()
    ctx.log_debug = MagicMock()
    
    return ctx
```

> **Note:** `ctx.task`, `ctx.task_name`, and `ctx.session_id` set above are test-only synthetic conveniences for this helper's own assertions — they are not real attributes on `AnyContext`/`Context` (`src/zrb/context/any_context.py`, `src/zrb/context/context.py`). Setting them here only works because `ctx` is a `MagicMock(spec=AnyContext)`, which permits assigning arbitrary attributes; production task code cannot rely on `ctx.task`/`ctx.task_name`/`ctx.session_id` being present.

```python
@pytest.mark.asyncio
async def test_with_realistic_context():
    from zrb import Task, Group
    
    group = Group(name="test")
    
    def my_action(ctx):
        name = ctx.input.name
        ctx.print(f"Hello, {name}!")
        return f"Processed: {name}"
    
    task = group.add_task(Task(name="greet", action=my_action))
    ctx = create_test_context(task, inputs={"name": "Alice"})
    
    result = await task._exec_action(ctx)
    assert result == "Processed: Alice"
    ctx.print.assert_called_once_with("Hello, Alice!")
```

---

## Testing Dependencies & Pipelines

To test task chains, create tasks and verify their upstream relationships:

```python
def test_task_dependencies():
    group = Group(name="test")
    
    task_a = group.add_task(CmdTask(name="a", cmd="echo A"))
    task_b = group.add_task(CmdTask(name="b", cmd="echo B", upstream=[task_a]))
    task_c = group.add_task(CmdTask(name="c", cmd="echo C", upstream=[task_a]))
    task_d = group.add_task(CmdTask(name="d", cmd="echo D", upstream=[task_b, task_c]))
    
    # Verify upstream relationships
    assert task_a in task_b.upstreams
    assert task_a in task_c.upstreams
    assert task_b in task_d.upstreams
    assert task_c in task_d.upstreams
```

---

## Running Tests

The recommended way to run tests in this repo is the project's `zrb-test.sh` script from the project root. It runs the full suite through `pytest`, additionally runs `flake8 src/zrb --select=F` (which fails on unused or duplicate imports), and enforces a minimum coverage gate of 90%:

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run all tests (pytest + flake8 F-checks + coverage gate)
./zrb-test.sh

# Scope to a file, directory, or a single test function
./zrb-test.sh test/task/test_base_task.py
./zrb-test.sh test/task/test_base_task.py::test_some_function
```

For a quicker, narrower check without the flake8/coverage gate, you can invoke `pytest` directly:

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest test/task/test_base_task.py

# Run with verbose output
poetry run pytest -v

# Run with coverage
poetry run pytest --cov=src/zrb
```

---

## Quick Reference

```python
# Test a Python task via mock context
ctx = MagicMock()
ctx.input.foo = "bar"
result = await task._exec_action(ctx)

# Test task dependencies
def test_pipeline(): 
    assert upstream_task in downstream_task.upstreams

# Run tests
poetry run pytest test/
```

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Testing Zrb Tasks
