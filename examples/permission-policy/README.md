# Permission Policy Example

This example demonstrates how to configure a custom `PermissionPolicy` for an `LLMChatTask`. 

A `PermissionPolicy` allows you to define fine-grained rules for tool execution based on **Capabilities** and **Tool Names**.

## How it works

In this example, we define a policy that:
1.  **Allows** all `READ` operations (e.g., `Read`, `LS`, `Glob`).
2.  **Denies** editing any `.env` files.
3.  **Forces confirmation** (`ASK`) for all shell commands (`Bash`), even if YOLO is ON.
4.  **Denies** everything else by default.

## Running the example

```bash
zrb llm chat --init examples/permission-policy/zrb_init.py "safe-chat"
```

Try asking the assistant to:
- "Read README.md" (Should be allowed immediately)
- "Edit .env" (Should be blocked silently)
- "Run ls" (Should prompt for approval)
