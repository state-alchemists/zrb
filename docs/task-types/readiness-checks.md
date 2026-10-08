🔖 [Documentation Home](../README.md) > [Task Types](./) > Readiness Checks

# Readiness Checks

A critical feature of Zrb is the ability to handle asynchronous, long-running processes cleanly.

If Task A starts a database server, it never "finishes." Task B (run migrations) cannot simply wait for Task A to complete. Instead, Task B must wait for Task A to become **Ready**.

Zrb handles this via the `readiness_check` parameter. A readiness check is a sub-task that runs concurrently alongside the main task. When the check succeeds, Zrb marks the main task as "ready" and immediately unblocks downstream successors.

> 💡 **Key Insight:** Readiness checks solve the "service startup" problem—waiting for services to be ready before proceeding.

---

## Table of Contents

- [`HttpCheck`](#1-httpcheck)
- [`TcpCheck`](#2-tcpcheck)
- [Advanced Monitoring](#advanced-readiness-monitoring)
- [Quick Reference](#quick-reference)

---

## 1. `HttpCheck`

`HttpCheck` verifies the readiness of an HTTP endpoint. It repeatedly polls a URL until it receives a `200 OK` status (or times out).

### When to Use

| Use Case | Example |
|----------|---------|
| Web servers | Apache, Nginx, dev servers |
| REST APIs | Backend services |
| Frontend dev servers | Vite, Webpack, Next.js |
| Integration tests | Wait for test fixtures |

### Example

```python
from zrb import CmdTask, HttpCheck, cli

# 1. Define the task that starts the server AND attach the check
start_server = cli.add_task(
    CmdTask(
        name="start-server",
        cmd="python -m http.server 8000",  # Long-running; the check decides when it is ready
        readiness_check=HttpCheck(
            name="check-server-status",
            url="http://localhost:8000",
        )
    )
)

# 2. Define the downstream task
test_server = cli.add_task(
    CmdTask(
        name="test-server",
        cmd="curl http://localhost:8000",
        upstream=[start_server]  # Waits for start_server to be READY
    )
)
```

---

## 2. `TcpCheck`

`TcpCheck` verifies that a TCP port on a host is open and accepting connections.

### When to Use

| Use Case | Example |
|----------|---------|
| Databases | PostgreSQL (5432), MySQL (3306), Redis (6379) |
| Message queues | RabbitMQ, Kafka |
| Custom protocols | Binary services |

### Example

```python
from zrb import CmdTask, TcpCheck, cli

# 1. Start the database and wait for port 5432
start_db = cli.add_task(
    CmdTask(
        name="start-db",
        cmd="docker compose up -d postgres",
        readiness_check=TcpCheck(
            name="check-db-port",
            host="localhost",
            port=5432,
        )
    )
)

# 2. Run migrations only after the TCP port accepts connections
run_migrations = cli.add_task(
    CmdTask(
        name="run-migrations",
        cmd="alembic upgrade head",
        upstream=[start_db]
    )
)
```

---

## Advanced Readiness Monitoring

By default, once a readiness check passes, Zrb assumes the service is up. However, services can crash.

You can instruct Zrb to continuously monitor the service and restart the main task if it goes down:

```python
reliable_server = cli.add_task(
    CmdTask(
        name="start-server",
        cmd="python -m http.server 8000",
        readiness_check=HttpCheck(name="check", url="http://localhost:8000"),
        
        # Advanced Monitoring
        monitor_readiness=True,       # Keep running HttpCheck in background
        readiness_check_period=5.0,   # Check every 5 seconds
        readiness_failure_threshold=3  # Restart after 3 failures
    )
)
```

### Readiness Parameters

Every task type accepts these:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `readiness_check` | `None` | Task(s) that probe readiness (e.g., HTTP check) |
| `readiness_check_delay` | `None` → 0.5s | Seconds to wait after starting the action before the first check. Unset, it comes from `ZRB_TASK_READINESS_DELAY` (milliseconds, default `500`) |
| `readiness_check_period` | `5` | Seconds between checks while monitoring (`monitor_readiness=True`) |
| `readiness_failure_threshold` | `1` | While monitoring, consecutive failed checks before the action is restarted |
| `readiness_timeout` | `None` → 60s | Seconds the readiness checks may take before the task fails. Caps the initial wait **and** each re-check round — see note below |
| `monitor_readiness` | `False` | Keep checking periodically *after* ready, and restart the action if the checks start failing |

> **`readiness_timeout` caps both waits.** Left unset (`None`), it takes its value from the `ZRB_TASK_READINESS_TIMEOUT` environment variable (milliseconds), which defaults to `60000` — so a readiness check that never completes fails the task after 60s instead of hanging the run. Set the parameter per task, or the environment variable to change the default for every task. An explicit `0` (or a negative value) removes the cap, and a check that never returns then waits forever.

---

## Quick Reference

| Check Type | Protocol | Example Use |
|------------|----------|-------------|
| `HttpCheck` | HTTP/HTTPS | Web servers, APIs |
| `TcpCheck` | TCP | Databases, Redis, message queues |

### HttpCheck Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `url` | URL to check | `http://localhost` |
| `http_method` | HTTP method | `GET` |
| `interval` | Seconds between polls | `5` (`ZRB_HTTP_CHECK_INTERVAL`, in ms) |

### TcpCheck Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `host` | Hostname | `localhost` |
| `port` | Port number | `80` |
| `interval` | Seconds between polls | `5` (`ZRB_TCP_CHECK_INTERVAL`, in ms) |

---

🔖 [Documentation Home](../README.md) > [Task Types](./) > Readiness Checks
