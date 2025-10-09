🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Session and Context](./README.md) > [Session](./session.md)

# The Session

A `Session` in Zrb is the conductor of your automation orchestra. When you run a Zrb command, a new session is born to manage the entire execution of your requested task and all its dependencies. It's the ephemeral environment where your workflow comes to life.

## What Does a Session Do?

The Session is a busy entity with several key responsibilities:

*   **Task Lifecycle Management:** It's the session's job to keep track of every task's status: is it waiting to run (`pending`), currently running, finished (`completed`), or did it run into trouble (`failed`)?
*   **Dependency Resolution:** The session reads the `upstream` dependencies you've defined and figures out the correct, logical order to execute your tasks.
*   **Context Provisioning:** Before a task runs, the session hands it a custom-built `Context` object, which is the task's toolkit for interacting with the Zrb environment.
*   **Deferred Execution:** It manages any asynchronous operations (`coroutines`) that need to be executed during the session.
*   **State Logging:** The session records the progress and state of all its tasks, which is crucial for monitoring and debugging.
*   **Shared Context Management:** It holds the `SharedContext`, which contains data (like inputs, environment variables, and XCom) that needs to be accessible to all tasks within that session.

## How It Works

When you run a task, Zrb creates a `Session` instance. This session identifies the main task and all its upstream dependencies. It then builds a plan of execution based on these dependencies.

As each task is ready to run, the session provides it with its `Context` object and executes its `action`. The session monitors the outcome and, upon successful completion, moves on to the next tasks in the workflow.

## Relationship to Tasks and Context

*   **Tasks** are the individual units of work. They are executed *within* a session.
*   The **Context** (`ctx`) is the bridge between a task and the session. It's how a task gets the information and tools it needs to do its job.

In short: the **Session** is the runtime, the **Task** is the action, and the **Context** is the interface connecting them.

For a deeper dive into the `Context` object, see the [Context documentation](./context.md).