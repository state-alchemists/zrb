🔖 [Documentation Home](../../../../README.md) > [Task](../../README.md) > [Core Concepts](../../../README.md) > [Task](../README.md) > [Task Types](./README.md) > HttpCheck

# `HttpCheck`

The `HttpCheck` task is a specialized tool for verifying the readiness of an HTTP endpoint. It's most commonly used as a `readiness_check` for tasks that start a web service, ensuring that the service is up and running before other tasks proceed.

## Example

Imagine you have a task that starts a web server. You can use `HttpCheck` to wait until the server is responding successfully before running your tests.

```python
from zrb import CmdTask, HttpCheck, cli

# A task that starts a web server in the background
start_server = CmdTask(
    name="start-server",
    description="Start a web server",
    cmd="python -m http.server 8000 &", # Run in background
    readiness_check=HttpCheck(
        name="check-server-status",
        description="Checks if the web server is available",
        url="http://localhost:8000",
        # You can customize other options too:
        # http_method="GET",
        # interval=5, # Check every 5 seconds
    )
)

# A task that runs only after the server is confirmed to be ready
test_server = Task(
    name="test-server",
    description="Runs a test against the server",
    action=lambda ctx: ctx.print("Server is ready, running tests!"),
    upstream=[start_server] # Depends on the server starting task
)

cli.add_task(start_server)
cli.add_task(test_server)
```

You can also run an `HttpCheck` task directly from the command line if you just want to verify an endpoint's status.

**When to use**: Use `HttpCheck` to make your workflows robust when dealing with web services. It's essential for orchestrating microservices, running integration tests, or any scenario where you need to wait for an HTTP endpoint to become available.