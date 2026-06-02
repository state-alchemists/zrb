🔖 [Home](../../README.md) > [Advanced Topics](./) > Plan Mode

# Plan Mode

Plan Mode is a read-only discovery state that allows LLM agents to safely explore a codebase, research solutions, and formulate a strategy before making any modifications.

---

## Table of Contents

- [Overview](#overview)
- [How it Works](#how-it-works)
- [Entering Plan Mode](#entering-plan-mode)
- [Exiting Plan Mode](#exiting-plan-mode)
- [Security: The Strict ASK Gate](#security-the-strict-ask-gate)

---

## Overview

When an agent is in Plan Mode, it is restricted by the `PLAN_MODE_POLICY`. This policy permits all `READ` and `NETWORK` operations but strictly denies `EDIT`, `EXECUTE`, and `DELEGATE` capabilities.

This ensures that the agent can read files, search the internet, and analyze code, but cannot:
-   Write or Edit files
-   Execute shell commands (`Bash`)
-   Run Zrb tasks
-   Spawn sub-agents

---

## How it Works

Plan Mode is an ambient state propagated via `ContextVars`. When active, `get_effective_policy()` returns the hardcoded `PLAN_MODE_POLICY`, overriding any task-level or global policy.

---

## Entering Plan Mode

You can trigger Plan Mode in two ways:

1.  **Slash Command:** Type `/plan` in the chat UI.
2.  **Tool Call:** The LLM can call the `EnterPlanMode` tool when it determines a task is complex or risky.

Once entered, the UI status bar will reflect the active mode:
`[Active mode: PLAN (read-only)]`

---

## Exiting Plan Mode

To exit Plan Mode and resume normal operation (BUILD mode), the LLM must call the `ExitPlanMode` tool and provide a concrete **Plan**.

The plan should be a bulleted list of proposed changes (e.g., "Add user authentication logic to src/auth.py", "Update unit tests").

---

## Security: The Strict ASK Gate

Exiting Plan Mode is a high-risk transition because it opens the execution gate. To protect against unauthorized "escapes," the `ExitPlanMode` tool is protected by a **Strict ASK** rule in the `PLAN_MODE_POLICY`.

**This means:**
-   The user **must** always manually approve the transition.
-   The transition **cannot** be auto-approved, even if YOLO mode is ON.
-   The user has the opportunity to review the proposed plan before any execution begins.

---
🔖 [Home](../../README.md) > [Advanced Topics](./) > Plan Mode
