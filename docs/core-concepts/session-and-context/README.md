🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Session and Context](./README.md)

# Session and Context

The concepts of `Session` and `Context` are central to how Zrb executes and manages your tasks. They provide the runtime environment and the bridge between your task's logic and the Zrb engine.

*   **[Session](./session.md):** A `Session` represents a single execution of a task workflow. It manages the entire lifecycle, from resolving dependencies to tracking the status of each task.

*   **[Context](./context.md):** The `Context` (or `ctx`) is an object passed to every task, acting as its interface to the session. Through the context, a task can access inputs, environment variables, and communicate with other tasks.

*   **[XCom](./xcom.md):** Short for Cross-Communication, `XCom` is the mechanism for tasks to pass data and results to each other within a session.