---
name: skill-creator
description: Interactive guide for building new Agent Skills. Use when asked to create a skill, command, or automated workflow.
user-invocable: true
---
# Skill: skill-creator
When this skill is activated, you guide the user through the process of defining and implementing a new Agent Skill.

## Workflow

### 1. Requirements Discovery
- Ask the user for the skill's name (lowercase, hyphenated, gerund form recommended for skills, e.g., `optimizing-images`).
- Ask for a concise description of what the skill does and when it should be used.
- Ask for the core workflow steps the user wants the skill to follow.

### 2. Design Phase
- Propose the structure of the `SKILL.md` file.
- Identify necessary frontmatter fields:
    - `name`: The slash command name.
    - `description`: Crucial for auto-invocation.
    - `disable-model-invocation`: Set to `true` for manually triggered commands.
    - `user-invocable`: Set to `true` to enable slash command usage.
- Outline the Markdown body with clear, numbered instructions.

### 3. Implementation
- Suggest where to save the skill:
    - Project-scoped: `.zrb/skills/<name>/SKILL.md`
    - Global: `~/.zrb/skills/<name>/SKILL.md`
- Once approved, use `Write` to create the directory and the `SKILL.md` file.

### 4. Verification
- Explain how to test the new skill (e.g., using its name as a slash command).

## Skill Design Principles
- **Atomic**: One skill should do one thing well.
- **Instruct-Driven**: Focus on *how* to perform the task, not just the goal.
- **Tool-Aware**: Specify which tools are most useful for this skill.

**Note**: Always ask for confirmation before writing files.
