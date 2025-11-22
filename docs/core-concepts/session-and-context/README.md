🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Session and Context](./README.md)

# Session and Context

The concepts of `Session` and `Context` are central to how Zrb executes and manages your tasks. They provide the runtime environment and the bridge between your task's logic and the Zrb engine.

*   **[Session](./session.md):** A `Session` represents a single execution of a task workflow. It manages the entire lifecycle, from resolving dependencies to tracking the status of each task.

*   **[Context](./context.md):** The `Context` (or `ctx`) is an object passed to every task, acting as its interface to the session. Through the context, a task can access inputs, environment variables, and communicate with other tasks.

*   **[XCom](./xcom.md):** Short for Cross-Communication, `XCom` is the mechanism for tasks to pass data and results to each other within a session.

---

## What's the Difference?

The distinction between a `Session` and a `Context` can be simplified with an analogy:

*   Think of the **`Session`** as the entire **factory assembly line** for a single product order. It's the whole process from start to finish, managing all the steps (tasks) and the overall state.
*   Think of the **`Context`** as the specific **toolbox and set of instructions** given to a worker at one particular station on that line. It contains only what the worker (the task) needs at that exact moment: the inputs to work on (`ctx.input`), the environment settings (`ctx.env`), and a way to pass the finished part to the next station (`ctx.xcom`).

In short:
- **Session**: Manages the *entire run* of a workflow.
- **Context**: Provides a *single task* with the data it needs to do its job.