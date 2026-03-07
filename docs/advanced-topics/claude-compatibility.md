🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Claude Code Compatibility

# Claude Code Compatibility

Zrb is designed to be highly compatible with **Claude Code** configurations. This allows you to leverage your existing Claude skills, agents, and hooks within Zrb's automated workflows.

---

## Table of Contents

- [Project Instructions](#1-project-instructions-claudemd)
- [Skills](#2-skills-skillmd)
- [Agents and Subagents](#3-agents-and-subagents-agentmd)
- [Hooks](#4-hooks-hooksjson)
- [Plugins](#5-plugins)
- [Quick Reference](#quick-reference)

---

## 1. Project Instructions (CLAUDE.md)

Zrb automatically detects and includes instructions from `CLAUDE.md` and `AGENTS.md` files. It searches from the filesystem root down to your current working directory, ensuring that all relevant project context is loaded into the LLM's system prompt.

> 💡 **Tip:** Use `AGENTS.md` for technical project documentation and `CLAUDE.md` for Claude-specific instructions.

---

## 2. Skills (SKILL.md)

Zrb supports Claude-style skills. A skill is defined by a `SKILL.md` (or `*.skill.md`) file.

### Discovery Paths

| Location | Type |
|----------|------|
| `~/.claude/skills/` | User-level (Claude) |
| `~/.zrb/skills/` | User-level (Zrb) |
| `./.claude/skills/` | Project-level (Claude) |
| `./.zrb/skills/` | Project-level (Zrb) |
| `ZRB_LLM_PLUGIN_DIRS` | Plugin directories |

### Skill Format

Skills can use YAML frontmatter for metadata:

```markdown
---
name: my-custom-skill
description: Performs a specialized task
user-invocable: true
---
# My Custom Skill

Detailed instructions for the LLM on how to perform this skill.
```

| Field | Description |
|-------|-------------|
| `name` | Skill identifier (becomes `/name` command) |
| `description` | Brief description |
| `user-invocable` | If `true`, becomes slash command in TUI |

---

## 3. Agents and Subagents (AGENT.md)

Zrb can spawn subagents defined in Claude-style `AGENT.md` (or `*.agent.md`) files.

### Discovery Paths

| Location | Type |
|----------|------|
| `~/.claude/agents/` | User-level (Claude) |
| `~/.zrb/agents/` | User-level (Zrb) |
| `./.claude/agents/` | Project-level (Claude) |
| `./.zrb/agents/` | Project-level (Zrb) |
| `ZRB_LLM_PLUGIN_DIRS` | Plugin directories |

### Agent Format

Agents use YAML frontmatter to define their identity and capabilities:

```markdown
---
name: specialized-coder
description: Expert in a specific domain
model: openai:gpt-4o
tools: [read_file, search_files]
---
# Specialized Coder Prompt

You are an expert coder specializing in...
```

| Field | Description |
|-------|-------------|
| `name` | Agent identifier |
| `description` | Brief description for delegation |
| `model` | LLM model for this agent |
| `tools` | List of available tools |

---

## 4. Hooks (hooks.json)

Zrb supports Claude-compatible lifecycle hooks.

### Discovery Paths

| Location | Type |
|----------|------|
| `~/.claude/hooks.json` | User-level single file |
| `~/.claude/hooks/*.json` | User-level directory |
| `~/.zrb/hooks.json` | User-level single file |
| `~/.zrb/hooks/*.json` | User-level directory |
| `./.claude/hooks.json` | Project-level single file |
| `./.zrb/hooks.json` | Project-level single file |

> 💡 **See Also:** [Hooks Guide](./hooks.md) for detailed hook configuration.

---

## 5. Plugins

Zrb's plugin system is built on top of these compatibility layers. By setting `ZRB_LLM_PLUGIN_DIRS` to a colon-separated list of paths, you can distribute and share collections of agents and skills that follow the Claude standard.

```bash
export ZRB_LLM_PLUGIN_DIRS="/opt/zrb-plugins:/home/user/my-plugins"
```

---

## Quick Reference

| Feature | File Pattern | Discovery Path |
|---------|--------------|----------------|
| Project Instructions | `CLAUDE.md`, `AGENTS.md` | Current dir → root |
| Skills | `SKILL.md`, `*.skill.md` | `skills/` directories |
| Agents | `AGENT.md`, `*.agent.md` | `agents/` directories |
| Hooks | `hooks.json`, `*.json` | `hooks/` directories |

---