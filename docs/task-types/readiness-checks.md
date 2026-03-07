🔖 [Documentation Home](../../README.md) > [Task Types](./) > Readiness Checks

# Readiness Checks

A critical feature of Zrb is the ability to handle asynchronous, long-running processes cleanly.

If Task A starts a database server, it never "finishes." Task B (run migrations) cannot simply wait for Task A to complete. Instead, Task B must wait for Task A to become **Ready**.

Zrb handles this via the `readiness_check` parameter. A readiness check is a sub-task that runs concurrently alongside the main task. When the check succeeds, Zrb marks the main task as "ready" and immediately unblocks downstream successors!

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
        cmd="python -m http.server 8000 &",  # Run in background
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
        cmd="python -m http.server 8000 &",
        readiness_check=HttpCheck(name="check", url="http://localhost:8000"),
        
        # Advanced Monitoring
        monitor_readiness=True,       # Keep running HttpCheck in background
        readiness_check_period=5.0,   # Check every 5 seconds
        readiness_failure_threshold=3  # Restart after 3 failures
    )
)
```

| Parameter | Description |
|-----------|-------------|
| `monitor_readiness` | Continue monitoring after initial success |
| `readiness_check_period` | Seconds between checks |
| `readiness_failure_threshold` | Failures before restart/cancel |

---

## Quick Reference

| Check Type | Protocol | Example Use |
|------------|----------|-------------|
| `HttpCheck` | HTTP/HTTPS | Web servers, APIs |
| `TcpCheck` | TCP | Databases, Redis, message queues |

### HttpCheck Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `url` | URL to check | Required |
| `http_method` | HTTP method | `GET` |
| `interval` | Seconds between retries | `1` |

### TcpCheck Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `host` | Hostname | Required |
| `port` | Port number | Required |
| `interval` | Seconds between retries | `1` |

---