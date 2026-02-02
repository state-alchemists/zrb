# Agents Configuration Directory

> Specialized agent configurations for ZRB project tasks.

---

## 📁 Available Agents

| Agent | Purpose | Location |
|-------|---------|----------|
| **Documentation** | Generate and maintain documentation | [`./documentation/AGENTS.md`](./documentation/AGENTS.md) |
| **Planning** | Project planning and task breakdown | [`./planning/AGENTS.md`](./planning/AGENTS.md) |
| **Testing** | Write and analyze tests | [`./testing/AGENTS.md`](./testing/AGENTS.md) |
| **Refactoring** | Code modernization and refactoring | [`./refactoring/AGENTS.md`](./refactoring/AGENTS.md) |
| **Research** | Academic research and journal writing | [`./research/AGENTS.md`](./research/AGENTS.md) |

---

## 🚀 Quick Start

### Using with LLMTask

```python
from zrb import LLMTask, StrInput
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

# Example: Using documentation agent
doc_task = LLMTask(
    name="generate-docs",
    description="Generate documentation",
    input=[StrInput(name="target", default="./src")],
    message="""
    Read the documentation agent guidelines from agents/documentation/AGENTS.md
    and generate comprehensive documentation for {ctx.input.target}.
    """,
    tools=[analyze_code, write_file],
)
```

### Using with Sub-Agent

```python
from zrb.llm.tool.sub_agent import run_sub_agent

# Delegate to specialized agent
result = await run_sub_agent(
    agent_config="agents/testing/AGENTS.md",
    task="Generate unit tests for src/zrb/task/base_task.py",
    context={"coverage_target": 90}
)
```

---

## 🏗️ Agent Structure

Each agent configuration includes:

1. **Purpose** - What the agent specializes in
2. **Tools** - Available tools and capabilities
3. **Tasks** - Common task templates with prompts
4. **Standards** - Coding/documentation standards
5. **Workflows** - Example task chains
6. **Checklists** - Quality checklists

---

## 🔧 Creating Custom Agents

To create a new specialized agent:

1. Create new folder: `agents/<agent-name>/`
2. Create `AGENTS.md` with:
   - Clear purpose statement
   - Tool configurations
   - Task templates
   - Quality standards
3. Link in this index

### Template for New Agent

```markdown
# <Name> Agent - AGENTS.md

> Agent configuration for <purpose> tasks.

## 🎯 Purpose

This agent specializes in...

## 🔧 Tools & Capabilities

### Primary Tools
- tool1
- tool2

## 📋 Tasks

### Task 1
Prompt template...

## ✅ Checklist
- [ ] Item 1
- [ ] Item 2

## 🔗 Related Agents
- `../other-agent/AGENTS.md`

---
*Last updated: YYYY-MM-DD*
```

---

## 📖 Best Practices

1. **Read Agent Config First** - Always read the relevant AGENTS.md before delegating tasks
2. **Provide Context** - Include file paths, requirements, and constraints
3. **Chain Agents** - Combine multiple agents for complex workflows
4. **Review Output** - Always review agent output before applying changes
5. **Iterate** - Use feedback to refine agent prompts

---

## 🔗 Related Documentation

- [Project AGENTS.md](../AGENTS.md) - Main project configuration
- [Documentation Agent](./documentation/AGENTS.md) - Documentation tasks
- [Planning Agent](./planning/AGENTS.md) - Planning tasks
- [Testing Agent](./testing/AGENTS.md) - Testing tasks
- [Refactoring Agent](./refactoring/AGENTS.md) - Refactoring tasks
- [Research Agent](./research/AGENTS.md) - Research and academic writing

---

*Last updated: 2026-02-02*
