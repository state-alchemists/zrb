# Zrb Hook System

## Overview

The Zrb Hook System provides a powerful, extensible way to intercept and modify LLM interactions. It offers 100% compatibility with Claude Code hooks while adding advanced features like matcher evaluation, priority-based execution, and multiple hook types.

## Key Features

- **Claude Code Compatibility**: Full support for all Claude Code hook events and formats
- **Thread-Safe Execution**: Built-in thread pool with timeout controls
- **Matcher Evaluation**: Field-based filtering with 7 operators
- **Priority System**: Control execution order of hooks
- **Multiple Hook Types**: Command, Prompt, and Agent hooks
- **Dual Discovery**: Load hooks from both `.zrb/` and `.claude/` directories
- **Environment Injection**: Automatic injection of context into hook scripts

## Architecture

### Core Components

1. **HookManager**: Singleton manager that discovers, loads, and executes hooks
2. **HookExecutor**: Thread-safe executor with timeout controls
3. **HookContext**: Rich context object with all event data
4. **HookResult/HookExecutionResult**: Standardized result formats

### Execution Flow

```
Event Triggered → HookManager.find_hooks() → Matcher Evaluation → 
Priority Sorting → ThreadPool Execution → Result Aggregation → 
Block Detection → Return Results
```

## Configuration

### Location

Hooks can be placed in:

1. **User Global**: `~/.zrb/hooks/` or `~/.zrb/hooks.json`
2. **Project Local**: `./.zrb/hooks/` or `./.zrb/hooks.json`
3. **Claude Code Compat**: `~/.claude/hooks/` or `~/.claude/hooks.json`
4. **Project Claude**: `./.claude/hooks/` or `./.claude/hooks.json`

### File Formats

- JSON (`.json`)
- YAML (`.yaml`, `.yml`)

### Configuration Schema

```yaml
name: string              # Unique hook name
events: array             # List of events to trigger on
type: string              # "command", "prompt", or "agent"
config: object            # Type-specific configuration
description: string       # Optional description
matchers: array           # Optional matchers for conditional execution
async: boolean            # Run asynchronously (default: false)
enabled: boolean          # Enable/disable hook (default: true)
timeout: integer          # Execution timeout in seconds
env: object               # Additional environment variables
priority: integer         # Execution priority (higher = earlier)
```

## Hook Types

### 1. Command Hooks

Execute shell commands or scripts. Ideal for integrations with external systems.

```json
{
  "type": "command",
  "config": {
    "command": "echo 'Hello World'",
    "shell": true,
    "working_dir": "/optional/path"
  }
}
```

**Features:**
- Shell command execution
- Environment variable injection
- Working directory support
- Timeout controls

### 2. Prompt Hooks

Run LLM prompts with template substitution from context.

```json
{
  "type": "prompt",
  "config": {
    "user_prompt_template": "Analyze: {{tool_name}} with input {{tool_input}}",
    "system_prompt": "You are an analyzer.",
    "model": "openai:gpt-4o-mini",
    "temperature": 0.0
  }
}
```

**Features:**
- Template substitution with context fields
- Configurable LLM model
- Temperature control
- JSON output parsing

### 3. Agent Hooks

Run agents with tools for complex decision-making.

```json
{
  "type": "agent",
  "config": {
    "system_prompt": "You are a security agent.",
    "tools": ["file_check", "network_scan"],
    "model": "openai:gpt-4o"
  }
}
```

**Features:**
- Agent with tools
- Configurable system prompt
- Tool selection
- Complex reasoning

## Matcher System

Matchers allow hooks to run only when specific conditions are met.

### Operators

1. **equals**: Exact string match
2. **not_equals**: Not equal to value
3. **contains**: Contains substring
4. **regex**: Matches regular expression
5. **glob**: Matches glob pattern
6. **starts_with**: Starts with string
7. **ends_with**: Ends with string

### Field Access

Use dot notation to access nested fields:
- `tool_name` - Current tool name
- `metadata.project` - Project from metadata
- `event_data.file.path` - Nested path in event data
- `session_id` - Current session ID

### Examples

```json
"matchers": [
  {
    "field": "tool_name",
    "operator": "equals",
    "value": "delete_files"
  },
  {
    "field": "metadata.environment",
    "operator": "not_equals",
    "value": "production"
  },
  {
    "field": "event_data.file_path",
    "operator": "glob",
    "value": "*.py"
  }
]
```

## Priority System

Hooks execute in priority order (higher priority first). This ensures critical hooks like security checks run before others.

```json
{
  "priority": 100  # High priority - runs first
}
```

## Blocking Decisions

Hooks can block execution by:

1. **Exit Code 2**: Command returns exit code 2
2. **JSON Decision**: Output contains `{"decision": "block"}`

### Blocking Example

```bash
#!/bin/bash
# security_check.sh
if [ "$CLAUDE_METADATA_ENVIRONMENT" = "production" ]; then
  echo '{"decision": "block", "reason": "Not allowed in production"}'
  exit 2
fi
```

## Environment Variables

Command hooks receive these environment variables:

### Core Variables
- `CLAUDE_HOOK_EVENT` - Hook event name
- `CLAUDE_CWD` - Current working directory
- `CLAUDE_SESSION_ID` - Session identifier
- `CLAUDE_TRANSCRIPT_PATH` - Transcript file path
- `CLAUDE_PERMISSION_MODE` - Permission mode

### Event-Specific Variables
- `CLAUDE_TOOL_NAME` - Tool name (PreToolUse, PostToolUse)
- `CLAUDE_TOOL_INPUT` - Tool input as JSON
- `CLAUDE_PROMPT` - User prompt (UserPromptSubmit)
- `CLAUDE_MESSAGE` - Message content
- `CLAUDE_TITLE` - Notification title
- `CLAUDE_AGENT_ID` - Agent identifier

### Context Variables
- `CLAUDE_EVENT_DATA` - Full event data as JSON
- `CLAUDE_METADATA_*` - Metadata fields (dot→underscore)
  - `metadata.project.name` → `CLAUDE_METADATA_PROJECT_NAME`

## Events Reference

### Session Events
- `SessionStart` - New session begins
- `SessionEnd` - Session ends

### Prompt Events
- `UserPromptSubmit` - User submits a prompt

### Tool Events
- `PreToolUse` - Before tool execution
- `PostToolUse` - After successful tool execution
- `PostToolUseFailure` - After tool failure
- `PermissionRequest` - Permission requested

### Agent Events
- `SubagentStart` - Subagent starts
- `SubagentStop` - Subagent stops

### System Events
- `Notification` - System notification
- `Stop` - Execution stops
- `TeammateIdle` - Teammate becomes idle
- `TaskCompleted` - Task completes
- `PreCompact` - Before compacting history

## API Usage

### Python API

```python
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.types import HookEvent

# Execute hooks for an event
results = await hook_manager.execute_hooks(
    event=HookEvent.PRE_TOOL_USE,
    event_data={"tool": "read_file", "path": "/etc/passwd"},
    metadata={"environment": "production"},
    tool_name="read_file",
    tool_input={"path": "/etc/passwd"}
)

# Check for blocking
if results and results[0].blocked:
    print(f"Blocked: {results[0].reason}")
```

### Manual Hook Registration

```python
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.interface import HookCallable, HookContext
from zrb.llm.hook.types import HookEvent

async def custom_hook(context: HookContext):
    print(f"Custom hook: {context.event}")
    return HookResult(success=True)

hook_manager.register(custom_hook, events=[HookEvent.PRE_TOOL_USE])
```

## Best Practices

### Security
1. **Validate Inputs**: Always validate inputs in hook scripts
2. **Timeouts**: Set reasonable timeouts for all hooks
3. **Error Handling**: Implement proper error handling
4. **Least Privilege**: Run hooks with minimal necessary permissions

### Performance
1. **Async Hooks**: Use `"async": true` for long-running hooks
2. **Matcher Efficiency**: Use specific matchers to avoid unnecessary execution
3. **Priority Planning**: Order hooks by importance and dependencies
4. **Caching**: Cache expensive operations when possible

### Reliability
1. **Idempotency**: Design hooks to be safely retryable
2. **Logging**: Log hook execution and decisions
3. **Monitoring**: Monitor hook performance and failures
4. **Testing**: Test hooks in isolation before deployment

## Migration from Claude Code

### File Location
- Move hooks from `~/.claude/hooks/` to `~/.zrb/hooks/` (or keep both)
- Zrb automatically discovers hooks in both locations

### Configuration Changes
- No changes needed for basic hooks
- Add `priority`, `matchers`, `timeout` for advanced features

### Script Changes
- Environment variables are automatically injected
- JSON output format remains compatible
- Exit code 2 still means "block"

## Troubleshooting

### Common Issues

1. **Hook not executing**: Check matchers, enabled flag, and event names
2. **Timeout errors**: Increase timeout or optimize hook performance
3. **Permission denied**: Check script permissions and working directory
4. **JSON parsing errors**: Ensure valid JSON output for modifications

### Debugging

Enable debug logging:
```bash
export ZRB_LOG_LEVEL=debug
zrb your-task
```

Check loaded hooks:
```python
from zrb.llm.hook.manager import hook_manager
print(f"Loaded hooks: {len(hook_manager._hook_configs)}")
```

## Examples

See the `examples/hooks/` directory for complete examples:
- Basic command hooks
- Security hooks with matchers
- Prompt review hooks
- Logging and analytics hooks
- Blocking decision hooks