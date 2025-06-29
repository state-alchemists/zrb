🔖 [Documentation Home](../../../README.md) > [Task](../../../README.md) > [Core Concepts](../../README.md) > [Task](../README.md) > [Task Types](./README.md) > TcpCheck

# `TcpCheck`

The `TcpCheck` task is a specialized tool for verifying that a TCP port on a host is open and accepting connections. It's an essential `readiness_check` for tasks that depend on network services like databases, message queues, or any custom server.

## Example

Here's how you can use `TcpCheck` to ensure a database is ready before running migrations.

```python
from zrb import CmdTask, TcpCheck, cli

# A task that starts a database container
start_database = CmdTask(
    name="start-database",
    description="Starts the database server",
    cmd="docker compose up -d database",
    readiness_check=TcpCheck(
        name="check-db-port",
        description="Checks if the database port is open",
        host="localhost", # The host to check (defaults to localhost)
        port=5432,      # The TCP port to check
        # You can customize other options too:
        # interval=3, # Check every 3 seconds
    )
)

# A task that runs migrations, but only after the TCP check succeeds
run_migrations = Task(
    name="run-migrations",
    description="Runs database migrations",
    action=lambda ctx: ctx.print("Database port is open, running migrations!"),
    upstream=[start_database] # Depends on the database starting task
)

cli.add_task(start_database)
cli.add_task(run_migrations)
```

You can also run a `TcpCheck` task directly from the command line to quickly check if a port is open.

**When to use**: Use `TcpCheck` to make your workflows more reliable when they depend on non-HTTP network services. It prevents tasks from failing simply because a required service hasn't finished starting up yet.