# Task

A Task represents a single unit of work within a Zrb project. Tasks are the fundamental building blocks of Zrb workflows, encapsulating specific actions that need to be performed. These actions can range from running shell commands to executing Python code or interacting with language models.

> **Important**: Only tasks that are registered to the CLI or its subgroups are accessible from the command line or web interface. Make sure to add your tasks to the CLI or a group that is added to the CLI.

## Table of Contents

- [Creating Tasks](creating_tasks.md)
- [Key Components](key_components.md)
- Task Types
  - [BaseTask](types/base_task.md)
  - [CmdTask](types/cmd_task.md)
  - [HttpCheck](types/http_check.md)
  - [LLMTask](types/llm_task.md)
  - [RsyncTask](types/rsync_task.md)
  - [Scaffolder](types/scaffolder.md)
  - [Scheduler](types/scheduler.md)
  - [Task](types/task.md)
  - [TcpCheck](types/tcp_check.md)
- [Readiness Checks](readiness_checks.md)
- [Complete Example](complete_example.md)