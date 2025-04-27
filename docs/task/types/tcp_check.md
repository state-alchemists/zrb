🔖 [Documentation Home](../../../README.md) > [Task](../../README.md) > [Task Types](../README.md) > TcpCheck

# TcpCheck

The `TcpCheck` task is a specialized task type used for checking the readiness of a TCP port on a specific host. It's commonly used as a `readiness_check` for other tasks that depend on a service listening on a TCP port (e.g., a database, a custom server).

Here's an example of how to use `TcpCheck`:

```python
from zrb import Task, TcpCheck, cli

# Define a TcpCheck task to check if a database port is open
check_database_port = TcpCheck(
    name="check-db-port",
    description="Checks if the database port is open",
    host="localhost", # The host to check (default is localhost)
    port=5432, # The TCP port to check
    interval=3 # Check every 3 seconds
)

# Define a task that depends on the database being accessible via TCP
run_database_migration = cli.add_task(
    Task(
        name="run-migrations",
        description="Runs database migrations after the DB is available",
        action=lambda ctx: ctx.print("Database port is open, running migrations!"),
        readiness_check=check_database_port, # Use the TcpCheck task as a readiness check
        readiness_timeout=120, # Wait up to 120 seconds for the port to be open
        readiness_check_period=5 # Check the readiness_check every 5 seconds
    )
)

# You can also run the TcpCheck task directly if needed
cli.add_task(check_database_port)
```

**When to use**: Use `TcpCheck` when you need to ensure that a specific TCP port on a host is open and accepting connections before a task can proceed. This is essential for workflows that interact with network services like databases, message queues, or custom servers.