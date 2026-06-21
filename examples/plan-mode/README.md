# Plan Mode Example

This example demonstrates how Plan Mode works with an `LLMChatTask`.

Plan Mode is a read-only discovery state that restricts LLM agents to safe operations (reading, searching, web research) while blocking edits, shell execution, and delegation.

## How it works

In this example, we apply a custom permission policy to the built-in `llm_chat` task (via `llm_chat.permissions`) that explicitly denies editing `.env` files — layered on top of Plan Mode's built-in restrictions.

Plan Mode can be toggled via:
- **Slash command:** `/plan` — type once to enter, again to exit
- **Keyboard shortcut:** `Ctrl+P`
- **Tool call:** The LLM can call `EnterPlanMode` / `ExitPlanMode` programmatically

When Plan Mode is active, the info bar displays `PLAN MODE: On` (blue).

## Running the example

```bash
cd examples/plan-mode
zrb llm chat
```

Try:
- Type `/plan` to enter Plan Mode — the LLM will be restricted to reads
- Ask the assistant to "Read README.md" (allowed)
- Ask the assistant to "Edit some file" (blocked — plan mode denies EDIT)
- Type `/plan` again to exit Plan Mode and resume normal execution
