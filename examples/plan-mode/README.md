# Plan Mode Example

This example demonstrates how Plan Mode works with an `LLMChatTask`.

Plan Mode is a read-only discovery state that restricts LLM agents to safe operations (reading, searching, web research) while blocking edits, shell execution, and delegation.

## How it works

In this example, we apply a custom permission policy to the built-in `llm_chat` task (via `llm_chat.permissions`) that denies editing `.env` files and allows reads. That policy governs normal mode only: while Plan Mode is active, its built-in read-only preset **replaces** your policy (it is not merged with it), and the custom policy applies again once you exit.

Plan Mode can be toggled via:
- **Slash command:** `/plan` — type once to enter, again to exit
- **Keyboard shortcut:** `Shift+Tab` (cycles normal → accept-edits → plan)
- **Tool call:** The LLM can call `EnterPlanMode` / `ExitPlanMode` programmatically

When Plan Mode is active, the info bar displays `Plan Mode: On` (blue in the default theme).

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
