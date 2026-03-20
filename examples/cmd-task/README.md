# Command Task Example

Shows how to run shell commands with `CmdTask`.

## Basic Usage

```python
from zrb import CmdTask, cli

cli.add_task(CmdTask(name="hello", cmd="echo 'Hello!'"))
```

Run with: `zrb hello`

## Input Variables

Use `{ctx.input.name}` to interpolate inputs:

```python
cmd="echo 'Hello, {ctx.input.name}!'"
```

## Running

```bash
cd examples/cmd-task

# Basic command
zrb hello

# With input
zrb greet --name "Alice"

# Figlet (requires figlet installed)
zrb figlet --message "HELLO"

# List home directory
zrb ls-home

# Environment variables
zrb env-check

# Retry example
zrb flaky

# Capture output
zrb capture
```

## CmdTask Options

| Option | Description |
|--------|-------------|
| `cmd` | Command to run |
| `cwd` | Working directory |
| `env` | Environment variables |
| `retry` | Number of retries on failure |
| `retry_interval` | Seconds between retries |

## Example: Git Status

```python
git_status = CmdTask(
    name="git-status",
    cmd="git status",
    cwd="/path/to/repo",
)
```

## Example: Python Script

```python
run_script = CmdTask(
    name="run",
    cmd="python script.py --input {ctx.input.file}",
    cwd="./scripts",
    env={"PYTHONPATH": "./lib"},
)
```
