# Permission Policy Example

This example demonstrates how to configure a custom `PermissionPolicy` on the built-in `llm_chat` task (via `llm_chat.permissions`).

A `PermissionPolicy` allows you to define fine-grained rules for tool execution based on **Capabilities** and **Tool Names**.

## How it works

In this example, we define a policy that:
1.  **Allows** all `READ` operations (e.g., `Read`, `LS`, `Glob`).
2.  **Denies** editing any `.env` file (the `Edit` rule matches the tool's `path` argument with `fnmatch`).
3.  **Forces confirmation** (`ASK`) for all shell commands (`Shell`), even if YOLO is ON.
4.  **Denies** everything else by default — including every other edit, web access, and sub-agent delegation.

Rules are checked in order and the **first match wins**, so put specific rules before the `*` catch-all.

## Running the example

```bash
cd examples/permission-policy
zrb llm chat
```

Try asking the assistant to:
- "Read README.md" (Should be allowed immediately)
- "Edit .env" (Should be blocked without a prompt; the model is told the call was not permitted)
- "Run `git status` in the shell" (Should prompt for approval — the `Shell` rule applies)
