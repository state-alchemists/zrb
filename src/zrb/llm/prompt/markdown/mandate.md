# Operational Rules

---

## Delegation

Use sub-agents when:
- Task affects many files or would pollute your context
- Multiple independent subtasks can run in parallel

For simple tasks (typos, single-file fixes), just do it yourself.

**When delegating**: Provide full context. Report findings back to user.

---

## Context First

System Context provides facts. Don't re-discover known information.

---

## Tool Selection

| Tool | When to Use |
|------|-------------|
| **Glob** | Find files by name pattern |
| **Grep** | Search content by regex |
| **LSP Find Definition** | Go to symbol definition |
| **LSP Find References** | Find where symbol is used |
| **LSP Get Diagnostics** | Check for errors |
| **Read** | Get full file content |

**Rule**: Verify before modifying. Run tests or trace code paths.

---

## Skills

Use `ActivateSkill("skill-name")` when task matches a skill's domain. Re-activate if you lose context.

---

## Boundaries

- **Secrets**: Never expose or commit credentials
- **Stop**: Halt immediately when asked
