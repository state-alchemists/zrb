# Readiness Checks

Readiness checks are special tasks that verify if a service or application is ready before proceeding with downstream tasks. Readiness checks are themselves tasks, meaning you can use any task type suitable for verification, such as `HttpCheck` or a custom Python task. For more information on different task types, see the [Task Types section in the Task documentation](../README.md#task-types). This is particularly useful for tasks that start services, servers, or containers.

Zrb provides built-in readiness check tasks:

## HttpCheck

Verifies that an HTTP endpoint is responding with a 200 status code:

```python
from zrb import CmdTask, HttpCheck, cli

# Start a web server and wait until it's ready
start_server = cli.add_task(
    CmdTask(
        name="start-server",
        description="Start the web server",
        cmd="python -m http.server 8000",
        readiness_check=HttpCheck(
            name="check-server",
            url="http://localhost:8000"
        )
    )
)

# This task will only run after the server is ready
test_server = cli.add_task(
    CmdTask(
        name="test-server",
        description="Test the web server",
        cmd="curl http://localhost:8000"
    )
)

start_server >> test_server
```

## TcpCheck

Verifies that a TCP port is open and accepting connections:

```python
from zrb import CmdTask, TcpCheck, cli

# Start a database and wait until it's ready
start_database = cli.add_task(
    CmdTask(
        name="start-database",
        description="Start the database",
        cmd="docker compose up -d database",
        readiness_check=TcpCheck(
            name="check-database",
            host="localhost",
            port=5432
        )
    )
)

# This task will only run after the database is ready
migrate_database = cli.add_task(
    CmdTask(
        name="migrate-database",
        description="Run database migrations",
        cmd="python migrate.py"
    )
)

start_database >> migrate_database
```

## Multiple Readiness Checks

You can specify multiple readiness checks for a single task:

```python
from zrb import CmdTask, HttpCheck, cli

# Start a microservices application and wait until all services are ready
start_app = cli.add_task(
    CmdTask(
        name="start-app",
        description="Start the application",
        cmd="docker compose up -d",
        readiness_check=[
            HttpCheck(name="check-api", url="http://localhost:3000/health"),
            HttpCheck(name="check-auth", url="http://localhost:3001/health"),
            HttpCheck(name="check-frontend", url="http://localhost:8080")
        ]
    )
)

# This task will only run after all services are ready
test_app = cli.add_task(
    CmdTask(
        name="test-app",
        description="Run integration tests",
        cmd="python test_integration.py"
    )
)

start_app >> test_app
```

## Readiness Check Parameters

When using readiness checks, you can configure their behavior with these parameters:

- **readiness_check_delay**: The delay in seconds before starting readiness checks (default: 0.5)
- **readiness_check_period**: The period in seconds between readiness checks (default: 5)
- **readiness_failure_threshold**: The number of consecutive failures allowed before considering the task failed (default: 1)

```python
from zrb import CmdTask, HttpCheck, cli

# Start a web application with custom readiness check parameters
start_app = cli.add_task(
    CmdTask(
        name="start-app",
        description="Start the web application",
        cmd="npm start",
        readiness_check=HttpCheck(name="check-app", url="http://localhost:3000"),
        readiness_check_delay=2.0,  # Wait 2 seconds before starting checks
        readiness_check_period=10.0,  # Check every 10 seconds
        readiness_failure_threshold=3  # Allow up to 3 failures before failing
    )
)
```

## Custom Readiness Checks

You can create custom readiness checks by using any task type. A readiness check is considered successful if it completes without raising an exception.

```python
from zrb import Task, CmdTask, cli

# Custom readiness check that verifies a specific condition
check_database_initialized = Task(
    name="check-database-initialized",
    description="Check if the database is initialized",
    action=lambda ctx: ctx.run_command("psql -c 'SELECT 1 FROM users LIMIT 1'")
)

# Start a database and use the custom check
start_database = cli.add_task(
    CmdTask(
        name="start-database",
        description="Start the database",
        cmd="docker compose up -d database",
        readiness_check=check_database_initialized
    )
)
```

## How Readiness Checks Work

When a task with readiness checks completes:

1. Zrb executes the readiness checks
2. If all checks pass, the task is considered complete and downstream tasks can run
3. If any check fails, Zrb will retry the checks according to the configured parameters
4. The task will only be considered complete when all readiness checks pass

This ensures that downstream tasks only run when the system is in the expected state, preventing race conditions and timing issues.

🔖 [Documentation Home](../../README.md) > [Task](../README.md) > Readiness Checks