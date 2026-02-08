# Hook System Quick Start

Get started with Zrb hooks in 5 minutes.

## 1. Create Your First Hook

Create a simple logging hook in `~/.zrb/hooks/logging.json`:

```json
[
  {
    "name": "simple-logger",
    "events": ["SessionStart", "SessionEnd"],
    "type": "command",
    "config": {
      "command": "echo 'Zrb hook: $CLAUDE_HOOK_EVENT at $(date)'",
      "shell": true
    },
    "description": "Log session events"
  }
]
```

## 2. Test the Hook

Run any Zrb task to see the hook in action:

```bash
zrb chat "Hello world"
```

You should see output like:
```
Zrb hook: SessionStart at Mon Feb 10 10:30:00 UTC 2025
```

## 3. Add a Tool Hook

Add a hook that runs before tools execute:

```json
{
  "name": "tool-notifier",
  "events": ["PreToolUse"],
  "type": "command",
  "config": {
    "command": "echo 'Tool $CLAUDE_TOOL_NAME called with input: $CLAUDE_TOOL_INPUT'",
    "shell": true
  },
  "description": "Notify when tools are used"
}
```

## 4. Add Conditional Execution

Use matchers to run hooks only when conditions are met:

```json
{
  "name": "production-check",
  "events": ["PreToolUse"],
  "type": "command",
  "config": {
    "command": "echo 'Running in production: $CLAUDE_TOOL_NAME'",
    "shell": true
  },
  "matchers": [
    {
      "field": "metadata.environment",
      "operator": "equals",
      "value": "production"
    }
  ]
}
```

## 5. Create a Blocking Hook

Create a security hook that blocks dangerous operations:

```json
{
  "name": "block-dangerous",
  "events": ["PreToolUse"],
  "type": "command",
  "config": {
    "command": "if [ \"$CLAUDE_TOOL_NAME\" = \"delete_files\" ]; then echo '{\"decision\": \"block\", \"reason\": \"Delete not allowed\"}'; exit 2; fi",
    "shell": true
  },
  "priority": 100,
  "description": "Block dangerous tools"
}
```

## 6. Use Prompt Hooks

Add an LLM-based review hook:

```json
{
  "name": "safety-review",
  "events": ["UserPromptSubmit"],
  "type": "prompt",
  "config": {
    "user_prompt_template": "Review: {{prompt}}",
    "system_prompt": "Check for safety issues.",
    "model": "openai:gpt-4o-mini"
  }
}
```

## 7. Project-Specific Hooks

Create project-local hooks in `./.zrb/hooks/project-hooks.json`:

```json
[
  {
    "name": "project-logger",
    "events": ["PreToolUse"],
    "type": "command",
    "config": {
      "command": "echo 'Project tool: $CLAUDE_TOOL_NAME' >> .zrb/tool-log.txt",
      "shell": true
    }
  }
]
```

## 8. Verify Hook Loading

Check which hooks are loaded:

```python
# Create a test script test_hooks.py
from zrb.llm.hook.manager import hook_manager

print(f"Total hooks loaded: {len(hook_manager._hook_configs)}")
for name, config in hook_manager._hook_configs.items():
    print(f"- {name}: {config.events}")
```

## Next Steps

1. **Explore Examples**: Check `examples/hooks/` for more patterns
2. **Read Documentation**: See `docs/hook-system.md` for full details
3. **Test Thoroughly**: Test hooks in development before production
4. **Monitor Performance**: Watch for timeout issues

## Common Use Cases

- **Security**: Block dangerous tools, require approvals
- **Logging**: Audit all tool usage, track sessions
- **Validation**: Check inputs before execution
- **Enhancement**: Improve prompts, add context
- **Integration**: Connect to external systems
- **Compliance**: Enforce policies, document decisions