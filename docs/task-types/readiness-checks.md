🔖 [Documentation Home](../../README.md) > [Task Types](./) > Readiness Checks

# Readiness Checks

A critical feature of Zrb is the ability to handle asynchronous, long-running processes cleanly. 

If Task A starts a database server, it never "finishes." Task B (run migrations) cannot simply wait for Task A to complete. Instead, Task B must wait for Task A to become **Ready**.

Zrb handles this via the `readiness_check` parameter. A readiness check is a sub-task that runs concurrently alongside the main task. When the check succeeds, Zrb marks the main task as "ready" and immediately unblocks downstream successors!

Zrb provides two built-in tasks specifically designed for this: `HttpCheck` and `TcpCheck`.

---

## 1. `HttpCheck`

`HttpCheck` verifies the readiness of an HTTP endpoint. It repeatedly polls a URL until it receives a `200 OK` status (or times out).

### When to use
Use `HttpCheck` to wait for web servers, REST APIs, or frontend dev servers to initialize before running integration tests or downstream services.

### Example

```python
from zrb import CmdTask, HttpCheck, cli

# 1. Define the task that starts the server AND attach the check
start_server = cli.add_task(
    CmdTask(
        name="start-server",
        cmd="python -m http.server 8000 &", # Run in background
        readiness_check=HttpCheck(
            name="check-server-status",
            url="http://localhost:8000",
            # Optional parameters:
            # http_method="GET",
            # interval=2, # Check every 2 seconds
        )
    )
)

# 2. Define the downstream task
test_server = cli.add_task(
    CmdTask(
        name="test-server",
        cmd="curl http://localhost:8000",
        upstream=[start_server] # Waits for start_server to be READY
    )
)
```

---

## 2. `TcpCheck`

`TcpCheck` verifies that a TCP port on a host is open and accepting connections. 

### When to use
Use `TcpCheck` to ensure databases (PostgreSQL, Redis, MySQL), message queues, or custom binary protocols are fully initialized before interacting with them.

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
            # interval=3
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

You can instruct Zrb to continuously monitor the service and restart the main task if it goes down using the `monitor_readiness` and `readiness_failure_threshold` flags on the main task.

```python
reliable_server = cli.add_task(
    CmdTask(
        name="start-server",
        cmd="python -m http.server 8000 &",
        readiness_check=HttpCheck(name="check", url="http://localhost:8000"),
        
        # Advanced Monitoring
        monitor_readiness=True,       # Keep running the HttpCheck in the background
        readiness_check_period=5.0,   # Check every 5 seconds
        readiness_failure_threshold=3 # If it fails 3 times, cancel and restart the CmdTask!
    )
)
```
