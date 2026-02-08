# Zrb Hook System Examples

This directory contains examples of hook configurations for the Zrb framework, with 100% compatibility with Claude Code hooks.

## Directory Structure

Hooks can be placed in either:
- `~/.zrb/hooks/` or `~/.zrb/hooks.json` (user-global)
- `./.zrb/hooks/` or `./.zrb/hooks.json` (project-local)
- `~/.claude/hooks/` or `~/.claude/hooks.json` (Claude Code compatibility)
- `./.claude/hooks/` or `./.claude/hooks.json` (Claude Code compatibility)

## Hook Configuration Format

Hooks are defined in JSON or YAML format. Each hook has the following structure:

```json
{
  "name": "hook-name",
  "events": ["EventName"],
  "type": "command|prompt|agent",
  "config": {
    // Type-specific configuration
  },
  "description": "Optional description",
  "matchers": [
    {
      "field": "field.path",
      "operator": "equals|not_equals|contains|regex|glob|starts_with|ends_with",
      "value": "value to match",
      "case_sensitive": true
    }
  ],
  "async": false,
  "enabled": true,
  "timeout": 30,
  "env": {
    "KEY": "value"
  },
  "priority": 0
}
```

## Available Events

Zrb supports all Claude Code hook events:

- `SessionStart` - When a new session begins
- `UserPromptSubmit` - When user submits a prompt
- `PreToolUse` - Before a tool is executed
- `PermissionRequest` - When permission is requested
- `PostToolUse` - After a tool executes successfully
- `PostToolUseFailure` - After a tool fails
- `Notification` - For system notifications
- `SubagentStart` - When a subagent starts
- `SubagentStop` - When a subagent stops
- `Stop` - When execution stops
- `TeammateIdle` - When a teammate becomes idle
- `TaskCompleted` - When a task completes
- `PreCompact` - Before compacting history
- `SessionEnd` - When a session ends

## Hook Types

### 1. Command Hooks
Execute shell commands or scripts.

```json
{
  "name": "security-check",
  "events": ["PreToolUse"],
  "type": "command",
  "config": {
    "command": "python3 /path/to/security_check.py",
    "shell": true,
    "working_dir": "/optional/working/dir"
  },
  "matchers": [
    {
      "field": "tool_name",
      "operator": "equals",
      "value": "dangerous_tool"
    }
  ],
  "priority": 100
}
```

### 2. Prompt Hooks
Run LLM prompts with context.

```json
{
  "name": "prompt-review",
  "events": ["UserPromptSubmit"],
  "type": "prompt",
  "config": {
    "user_prompt_template": "Review this user prompt for safety: {{prompt}}",
    "system_prompt": "You are a safety reviewer. Check for harmful content.",
    "model": "openai:gpt-4o-mini",
    "temperature": 0.0
  }
}
```

### 3. Agent Hooks
Run agents with tools.

```json
{
  "name": "agent-review",
  "events": ["PreToolUse"],
  "type": "agent",
  "config": {
    "system_prompt": "You are a security agent. Review tool calls for safety.",
    "tools": ["file_read", "network_check"],
    "model": "openai:gpt-4o"
  }
}
```

## Matcher Operators

Matchers allow hooks to run only when specific conditions are met:

- `equals` - Exact match
- `not_equals` - Not equal to value
- `contains` - Contains substring
- `regex` - Matches regular expression
- `glob` - Matches glob pattern
- `starts_with` - Starts with string
- `ends_with` - Ends with string

Fields can use dot notation to access nested context:
- `tool_name` - Name of the tool being called
- `metadata.project` - Project name from metadata
- `event_data.file_path` - File path from event data

## Priority System

Hooks execute in priority order (higher priority first). Use this to ensure critical hooks (like security checks) run before others.

## Blocking Decisions

Hooks can block execution by:
1. Returning exit code 2
2. Outputting JSON with `"decision": "block"`

Example blocking hook:
```bash
#!/bin/bash
echo '{"decision": "block", "reason": "Tool not allowed in production"}'
exit 2
```

## Environment Variables

Command hooks receive these environment variables:
- `CLAUDE_HOOK_EVENT` - The hook event name
- `CLAUDE_CWD` - Current working directory
- `CLAUDE_TOOL_NAME` - Tool name (for tool events)
- `CLAUDE_TOOL_INPUT` - Tool input as JSON
- `CLAUDE_PROMPT` - User prompt (for prompt events)
- `CLAUDE_EVENT_DATA` - Full event data as JSON

## Examples in this Directory

- `basic-command-hook.json` - Simple command hook example
- `security-hook.json` - Security check with matchers
- `prompt-review-hook.json` - LLM prompt review
- `logging-hook.json` - Logging all tool calls
- `blocking-hook.json` - Blocking dangerous operations