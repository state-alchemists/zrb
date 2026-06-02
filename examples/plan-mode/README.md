# Plan Mode Example

This example demonstrates how Plan Mode works with an `LLMChatTask`.

Plan Mode is a read-only discovery state that restricts LLM agents to safe operations (reading, searching, web research) while blocking edits, shell execution, and delegation.

## How it works

In this example, we create a chat task with a custom permission policy that explicitly denies editing `.env` files — layered on top of Plan Mode's built-in restrictions.

Plan Mode can be toggled via:
- **Slash command:** `/plan` — type once to enter, again to exit
- **Keyboard shortcut:** `Ctrl+P`
- **Tool call:** The LLM can call `EnterPlanMode` / `ExitPlanMode` programmatically

When Plan Mode is active, the info bar displays `PLAN MODE: On` (blue).

## Running the example

```bash
zrb llm chat --init examples/plan-mode/zrb_init.py "safe-explorer"
```

Try:
- Type `/plan` to enter Plan Mode — the LLM will be restricted to reads
- Ask the assistant to "Read README.md" (allowed)
- Ask the assistant to "Edit some file" (blocked — plan mode denies EDIT)
- Type `/plan` again to exit Plan Mode and resume normal execution
