🔖 [Home](../../README.md) > [Documentation](../README.md) > [Advanced Topics](README.md) > [Claude Code Compatibility](claude-compatibility.md)

# Claude Code Compatibility

Zrb is designed to be highly compatible with **Claude Code** configurations. This allows you to leverage your existing Claude skills, agents, and hooks within Zrb's automated workflows.

## 1. Project Instructions (CLAUDE.md)

Zrb automatically detects and includes instructions from `CLAUDE.md` files. It searches from the filesystem root down to your current working directory, ensuring that all relevant project context is loaded into the LLM's system prompt.

## 2. Skills (SKILL.md)

Zrb supports Claude-style skills. A skill is defined by a `SKILL.md` (or `*.skill.md`) file.

### Discovery Paths
Zrb scans the following locations for skills:
-   `~/.claude/skills/`
-   `~/.zrb/skills/`
-   `./.claude/skills/`
-   `./.zrb/skills/`
-   Any directory in `ZRB_LLM_PLUGIN_DIRS` containing a `skills/` folder.

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

If `user-invocable` is set to `true`, the skill automatically becomes available as a slash command (e.g., `/my-custom-skill`) in the Zrb Chat TUI.

## 3. Agents and Subagents (AGENT.md)

Zrb can spawn subagents defined in Claude-style `AGENT.md` (or `*.agent.md`) files.

### Discovery Paths
-   `~/.claude/agents/`
-   `~/.zrb/agents/`
-   `./.claude/agents/`
-   `./.zrb/agents/`
-   Any directory in `ZRB_LLM_PLUGIN_DIRS` containing an `agents/` folder.

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

## 4. Hooks (hooks.json)

As of version 2.2.0, Zrb supports Claude-compatible lifecycle hooks.

### Discovery Paths
-   `~/.claude/hooks.json` or `~/.claude/hooks/*.json`
-   `~/.zrb/hooks.json` or `~/.zrb/hooks/*.json`
-   `./.claude/hooks.json` or `./.claude/hooks/*.json`
-   `./.zrb/hooks.json` or `./.zrb/hooks/*.json`

See the [Hooks Guide](./hooks.md) for more details.

## 5. Plugins

Zrb's plugin system is built on top of these compatibility layers. By setting `ZRB_LLM_PLUGIN_DIRS` to a colon-separated list of paths, you can distribute and share collections of agents and skills that follow the Claude standard.

---
🔖 [Home](../../README.md) > [Documentation](../README.md) > [Advanced Topics](README.md) > [Claude Code Compatibility](claude-compatibility.md)
