🔖 [Documentation Home](../../../README.md) > [Task](../../../README.md) > [Core Concepts](../../README.md) > [Task](../README.md) > [Task Types](./README.md) > HttpCheck

# HttpCheck

The `HttpCheck` task is a specialized task type used for checking the readiness of an HTTP endpoint. It's commonly used as a `readiness_check` for other tasks that depend on a web service being available.

Here's an example of how to use `HttpCheck`:

```python
from zrb import Task, HttpCheck, cli

# Define an HttpCheck task to check a web service endpoint
check_my_service = HttpCheck(
    name="check-service-status",
    description="Checks if the web service is available",
    url="http://localhost:8080/health", # The URL to check
    http_method="GET", # The HTTP method to use (default is GET)
    interval=5 # Check every 5 seconds
)

# Define a task that depends on the web service being ready
use_my_service = cli.add_task(
    Task(
        name="use-service-after-check",
        description="Performs an action after the service is confirmed ready",
        action=lambda ctx: ctx.print("Web service is ready, proceeding with task!"),
        readiness_check=check_my_service, # Use the HttpCheck task as a readiness check
        readiness_timeout=60, # Wait up to 60 seconds for the service to be ready
        readiness_check_period=5 # Check the readiness_check every 5 seconds
    )
)

# You can also run the HttpCheck task directly if needed
cli.add_task(check_my_service)
```

**When to use**: Use `HttpCheck` when you need to ensure that a web service or HTTP endpoint is accessible and returning a successful status code (by default, 200) before proceeding with a task. It's particularly useful in scenarios involving microservices or external APIs.