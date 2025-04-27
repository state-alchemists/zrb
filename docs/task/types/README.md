🔖 [Documentation Home](../../../README.md) > [Task](../../README.md) > Task Types

# Task Types

Zrb provides several built-in task types to handle various operations. These specialized task types extend the base `Task` (or `BaseTask`) and offer domain-specific features for common use cases.

You can directly instantiate these task types when defining your workflows.

Here are the available built-in task types:

- [`BaseTask`](./base_task.md): The fundamental building block for all other task types.
- [`CmdTask`](./cmd_task.md): For executing shell commands.
- [`HttpCheck`](./http_check.md): For performing HTTP health checks.
- [`LLMTask`](./llm_task.md): For integrating with Language Model APIs.
- [`RsyncTask`](./rsync_task.md): For synchronizing files and directories using rsync.
- [`Scaffolder`](./scaffolder.md): For creating files and directories from templates.
- [`Scheduler`](./scheduler.md): For triggering tasks based on a defined schedule.
- [`Task`](./task.md): An alias for `BaseTask`, commonly used for general Python tasks.
- [`TcpCheck`](./tcp_check.md): For performing TCP port health checks.

[Back to Task Documentation](../README.md)