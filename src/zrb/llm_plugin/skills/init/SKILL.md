---
name: init
description: Initialize a new project or workspace for Claude Code compatibility. Generates a CLAUDE.md guide based on codebase analysis. Use when setting up a new project or generating AI assistant guidelines.
disable-model-invocation: true
user-invocable: true
---
# Skill: init
When this skill is activated, you prepare the current project for optimized interaction with Claude Code.

## Workflow
1.  **Codebase Analysis**: Use `LS`, `Glob`, and `Read` to identify the project's language, architecture, core dependencies, and established patterns.
2.  **Generate CLAUDE.md**: Create a `CLAUDE.md` guide in the project root. This file must serve as the authoritative reference for:
    - **Project Overview**: What is this project?
    - **Core Concepts**: Key architectural decisions and domain models.
    - **Development Workflow**: Specific commands for building, testing, and running.
    - **Style & Conventions**: Naming rules, indentation, and idiomatic patterns.
3.  **Zrb Setup**: Suggest creating a `zrb_init.py` if custom automation tasks are needed.

**Note**: Always present the proposed `CLAUDE.md` content to the user for approval before writing the file.
