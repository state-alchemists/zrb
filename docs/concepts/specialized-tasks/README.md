🔖 [Table of Contents](../../README.md) / [Concepts and Terminologies](../README.md)

# Specialized Tasks

You have learned about `Task` and `CmdTask`. The general rule is as follows:

- If writing your workflow in Python is easier, use `Task` or `@python_task` decorator.
- If writing your workflow in Shell script is more effortless, use `CmdTask`.

Aside from `Task` and `CmdTask`, Zrb has multiple specialized Tasks.


- [DockerComposeTask](docker-compose-task.md): Use this Task Class to deal with Docker Compose-related workflow.
- [ResourceMaker](resource-maker.md): Use this Task to generate Code, module, etc.
- [Notifier](notifider.md): Use this Task to notify the user about anything locally.
- [RsyncTask](rsync-task.md): Use this Task to copy from/to remote computers.
- [Server](server.md): Use this Task to run a specific Task whenever some conditions are met.
- [Checker](checker.md): Use this Task to check other Task readiness or as `Server`'s trigger'.
- [FlowTask](flow-task.md): Use this Task to combine several unrelated Tasks into a single workflow.

🔖 [Table of Contents](../../README.md) / [Concepts and Terminologies](../README.md)
