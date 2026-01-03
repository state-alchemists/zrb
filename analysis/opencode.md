# OpenCode Prompt System Analysis

## Overview
OpenCode is a comprehensive AI-powered development platform with a sophisticated agent-based architecture. It uses YAML frontmatter for agent configuration and Markdown content for agent instructions, creating a flexible and human-readable system for defining specialized AI agents.

## Core Architecture

### 1. Agent Definition System
OpenCode agents are defined using a combination of YAML frontmatter and Markdown content:

```markdown
---
# YAML frontmatter for configuration
description: ALWAYS use this when writing docs
mode: primary
hidden: true
model: opencode/claude-haiku-4-5
tools:
  "*": false
  "github-triage": true
---

# Markdown content for agent instructions
You are a triage agent responsible for triaging github issues.

Use your github-triage tool to triage issues.

## Labels
...
```

### 2. Agent Configuration (YAML Frontmatter)
Key configuration options:

- **`description`**: When to use the agent
- **`mode`**: Agent mode (primary, secondary, etc.)
- **`hidden`**: Whether the agent is hidden from UI
- **`model`**: Specific model to use for this agent
- **`tools`**: Tool permissions (allow/deny specific tools)

### 3. Agent Instructions (Markdown Content)
- Natural language instructions for the agent
- Specific guidelines and constraints
- Tool usage instructions
- Workflow definitions

## Agent Types and Examples

### 1. Documentation Agent (`docs.md`)
**Purpose**: Expert technical documentation writing
**Key Features**:
- Not verbose, relaxed and friendly tone
- Specific formatting rules (title length, description style)
- Content structure guidelines (section dividers, title capitalization)
- Code snippet formatting rules
- Commit message prefixing (`docs:`)

### 2. Triage Agent (`triage.md`)
**Purpose**: GitHub issue triage and labeling
**Key Features**:
- Uses specific `github-triage` tool
- Detailed label assignment rules (windows, perf, desktop, nix, zen, docs, opentui)
- Team member assignment rules based on labels
- Clear criteria for when to apply each label

### 3. Git Committer Agent (`git-committer.md`)
**Purpose**: Git operations and commit management
**Key Features**:
- (Content not examined, but likely handles git workflows)

### 4. CSS Agent (`css.md`)
**Purpose**: CSS-related tasks
**Key Features**:
- (Content not examined, but likely specialized for CSS work)

## Technical Implementation

### 1. File Structure
```
.opencode/agent/          # Project agent definitions
  docs.md                # Documentation agent (YAML + Markdown)
  triage.md              # Triage agent (YAML + Markdown)
  git-committer.md       # Git committer agent
  css.md                 # CSS agent

packages/opencode/src/   # Core implementation
  session/prompt.ts      # Prompt construction and session management
  agent/agent.ts         # Agent implementation and lifecycle
  cli/cmd/agent.ts       # CLI commands for agent invocation
  acp/agent.ts           # Agent Control Protocol
  utils/prompt.ts        # Prompt utility functions
```

### 2. Prompt Construction
Based on file names and structure:
- **`session/prompt.ts`**: Likely handles dynamic prompt assembly
- **`utils/prompt.ts`**: Utility functions for prompt manipulation
- **Context management**: Session-based context with history

### 3. Tool Integration
- **Tool-specific permissions**: Granular control over which tools each agent can use
- **GitHub integration**: Specialized tools for GitHub operations
- **Development tools**: Integration with coding and documentation tools

## Comparison with Zrb and gemini-cli

### Unique Features of OpenCode
1. **YAML+Markdown agent definitions**: Human-readable, easy to edit
2. **Project-level agent customization**: Agents defined per project in `.opencode/agent/`
3. **Tool permission system**: Fine-grained control over agent tool access
4. **Model specification per agent**: Different models for different tasks
5. **Mode system**: Primary/secondary agent modes

### Similarities with Other Systems
1. **Agent specialization**: Like gemini-cli, uses specialized agents for specific tasks
2. **Context management**: Similar to Zrb's contextual notes
3. **Workflow definitions**: Structured workflows for common development tasks

## Usage Patterns

### Defining a New Agent
```markdown
---
description: Use for code review tasks
mode: secondary
model: opencode/claude-sonnet-4-5
tools:
  "*": false
  "code-review": true
  "git-diff": true
---

You are a code review agent.

## Responsibilities
- Review pull request code changes
- Check for code quality issues
- Ensure coding standards are followed
- Suggest improvements

## Constraints
- Only comment on code, not process
- Be constructive, not critical
- Reference specific line numbers
```

### Agent Invocation
```bash
# Likely CLI patterns
opencode agent docs --file=README.md
opencode agent triage --issue=123
opencode agent git-committer --message="Fix bug"
```

## Strengths

1. **Human-readable configuration**: YAML+Markdown is accessible and easy to modify
2. **Project-specific customization**: Tailor agents to project needs
3. **Fine-grained tool control**: Precise control over agent capabilities
4. **Model optimization**: Use appropriate models for different tasks
5. **Clear agent boundaries**: Each agent has well-defined responsibilities

## Areas for Improvement (from Zrb's perspective)

1. **Global agent templates**: Could benefit from reusable agent templates
2. **Dynamic context injection**: Like gemini-cli's runtime context assembly
3. **Policy engine**: Tool execution governance
4. **Visual diff workflows**: IDE integration for change review
5. **Model routing**: Intelligent model selection

## Key Insights for Zrb

1. **YAML+Markdown format**: Consider adopting this human-readable format for workflow definitions
2. **Project-level customization**: Allow users to define custom workflows per project
3. **Tool permission system**: Granular control over which tools workflows can use
4. **Agent specialization**: More specialized personas for specific tasks
5. **Model specification**: Allow different models for different workflow types

## Summary
OpenCode implements a sophisticated yet accessible agent system using YAML+Markdown for configuration. Its strength lies in the balance between power and usability—complex agents can be defined in a format that's easy to read, write, and modify. The project-level agent definitions allow for deep customization, while the tool permission system provides safety and control.

For Zrb, the key takeaways are:
1. **Human-readable workflow definitions**: Consider YAML+Markdown format
2. **Project-level customization**: Allow per-project workflow definitions
3. **Granular tool control**: Fine-grained permissions for workflows
4. **Specialized agents/personas**: More focused personas for specific tasks
5. **Model optimization**: Task-appropriate model selection