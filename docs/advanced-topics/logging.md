🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Logging

# Logging in Zrb

Zrb has two independent logging systems:

1. **Python logging module** — structured logs for internal diagnostics (agent runs, approvals, hook execution)
2. **Task-level context logging** — per-task output visible during `zrb` CLI execution

---

## Table of Contents

- [Python Logging](#python-logging)
- [Task-Level Context Logging](#task-level-context-logging)
- [Session Log Directory](#session-log-directory)
- [Quick Reference](#quick-reference)

---

## Python Logging

Zrb uses Python's built-in `logging` module for internal diagnostics. The root logger is exposed as `CFG.LOGGER` and configured at CLI startup.

### Controlling Verbosity: `ZRB_LOGGING_LEVEL`

Set the environment variable to control log verbosity:

```bash
export ZRB_LOGGING_LEVEL=DEBUG   # Most verbose
export ZRB_LOGGING_LEVEL=INFO    # General operational messages
export ZRB_LOGGING_LEVEL=WARNING # Only warnings and errors (default)
export ZRB_LOGGING_LEVEL=ERROR   # Only errors
export ZRB_LOGGING_LEVEL=CRITICAL # Only critical errors
```

Valid values: `CRITICAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET`.

### Log Output Format

```
2026-06-01 14:30:00 DEBUG: Running agent step 42
2026-06-01 14:30:01 INFO: Tool call approved
2026-06-01 14:30:02 WARNING: Rate limit approaching
```

Format: `%(asctime)s %(levelname)s: %(message)s` (ISO-8601 date, styled with faint ANSI coloring).

### Root Logger (`CFG.LOGGER`)

Access the configured root logger from any module:

```python
from zrb.config.config import CFG

CFG.LOGGER.debug("Debug message")
CFG.LOGGER.info("Info message")
CFG.LOGGER.warning("Warning message")
CFG.LOGGER.error("Error message")
```

This is the same logger configured by `serve_cli()` in `zrb/__main__.py`. Output goes to stderr with a `StreamHandler` and `FaintFormatter`.

### Named Loggers

Some modules create their own named loggers via `logging.getLogger(__name__)`. These inherit the root logger's settings:

| Logger Name | Module |
|---|---|
| `zrb.util.dir_search` | `src/zrb/util/dir_search.py` |
| `zrb.llm.hook.*` | Hook system (loader, executor, manager, matcher) |
| `zrb.llm.snapshot.manager` | Snapshot system |
| `zrb.llm.ui.*` | UI implementations |

### Common Debugging Usage

The agent runner and approval channels use `CFG.LOGGER.debug()` extensively. Set `ZRB_LOGGING_LEVEL=DEBUG` to see:

- Tool approval decisions and deferral paths
- Agent run lifecycle (step execution, retries)
- Tool call arguments and results
- History compaction and summarization
- Approval channel multiplexing

---

## Task-Level Context Logging

Zrb tasks have built-in logging methods on the `Context` object, independent of the Python logging module. These print formatted messages to stderr during task execution:

```python
ctx.log_debug("Starting task")
ctx.log_info("Processing item %d", item_id)
ctx.log_warning("Disk space low")
ctx.log_error("Failed to connect")
ctx.log_critical("Fatal error")
```

| Method | Level Gate | Output Style |
|---|---|---|
| `log_debug(msg)` | `<= DEBUG` | `[DEBUG]` in faint style |
| `log_info(msg)` | `<= INFO` | `[INFO]` in faint style |
| `log_warning(msg)` | `<= INFO` | `[WARNING]` in bold yellow |
| `log_error(msg)` | `<= ERROR` | `[ERROR]` in bold red |
| `log_critical(msg)` | `<= CRITICAL` | `[CRITICAL]` in bold red |

The level gate is controlled by `CFG.LOGGING_LEVEL` (or an override on the `SharedContext`).

### Task vs Python Logging

| Aspect | Python Logging | Context Logging |
|---|---|---|
| Mechanism | `logging.Logger` | `Context` methods |
| Output | stderr, faint-styled | stderr, color-coded |
| Purpose | Internal diagnostics | Task execution feedback |
| Format | `asctime LEVEL: msg` | `[LEVEL] msg` |
| Filtering | `ZRB_LOGGING_LEVEL` | `ZRB_LOGGING_LEVEL` |

---

## Session Log Directory

Zrb persists session state (task execution records, LLM chat history) to disk:

| Variable | Default | Description |
|---|---|---|
| `ZRB_SESSION_LOG_DIR` | `~/.zrb/session` | Directory for session logs and execution history |

These are JSON records of task runs, not Python log output. They are used internally for session restore and audit trails.

---

## Quick Reference

```bash
# Full debug output (agent decisions, tool calls, approvals)
export ZRB_LOGGING_LEVEL=DEBUG
zrb llm chat

# Quiet mode (only warnings and errors)
export ZRB_LOGGING_LEVEL=WARNING
zrb llm chat

# Custom session log directory
export ZRB_SESSION_LOG_DIR=/var/log/zrb-sessions
```

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Logging
