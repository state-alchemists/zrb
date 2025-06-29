🔖 [Home](../../../README.md) > [Documentation](../../../../README.md) > [Core Concepts](../../README.md) > [Session and Context](./README.md) > [Session](./session.md)

# Session

A Session in Zrb represents a single execution environment for your tasks. When you run a Zrb command, a new session is created to manage the execution of the requested task and all its dependencies. The session orchestrates the workflow, tracks task statuses, and provides the necessary context for tasks to run.

## Key Responsibilities of a Session

Based on the Zrb core implementation, a Session handles several key aspects of task execution:

*   **Task Lifecycle Management:** Tracks the status of each task (e.g., pending, running, completed, failed, skipped, terminated) using `TaskStatus` objects.
*   **Dependency Resolution:** Determines the order in which tasks should be executed based on their defined `upstream` dependencies.
*   **Context Provisioning:** Provides a unique `Context` object to each task when it runs, containing task-specific and shared information.
*   **Deferred Execution:** Manages coroutines (asynchronous operations) that need to be executed later in the session lifecycle.
*   **State Logging:** Records the state and progress of the session and its tasks, often used for monitoring and history.
*   **Shared Context Management:** Holds the `SharedContext` which contains data accessible by all tasks within the session, such as inputs, environment variables, and XCom data.

## How Sessions Work

When you initiate a Zrb task from the CLI or web interface, a `Session` instance is created. This session identifies the main task to be run and registers it along with all its upstream dependencies. The session then uses the dependency information to determine the correct execution order.

As tasks are ready to run, the session provides them with their specific `Context` object. The task's `action` is then executed within this context. The session monitors the task's status and proceeds with the next tasks in the workflow once dependencies are met and readiness checks pass.

## Relation to Tasks and Context

Tasks are the units of work, and they are executed *within* a session. The session provides the runtime environment.

The `Context` object is the interface through which a task interacts with the session and accesses data. Each task receives its own `Context` instance from the session via the `ctx` parameter in its `action` method. This context includes access to the `SharedContext` of the session.

For more details on the `Context` object and the data it provides to tasks, see the [Context documentation](context.md).