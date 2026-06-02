🔖 [Home](../../README.md) > [Advanced Topics](./) > Plan Mode

# Plan Mode

Plan Mode is a read-only discovery state that allows LLM agents to safely explore a codebase, research solutions, and formulate a strategy before making any modifications.

---

## Table of Contents

- [Overview](#overview)
- [How it Works](#how-it-works)
- [Toggling Plan Mode](#toggling-plan-mode)
- [Security: The Strict ASK Gate](#security-the-strict-ask-gate)

---

## Overview

When an agent is in Plan Mode, it is restricted by the `PLAN_MODE_POLICY`. This policy permits all `READ` and `NETWORK` operations but strictly denies `EDIT`, `EXECUTE`, and `DELEGATE` capabilities.

This ensures that the agent can read files, search the internet, and analyze code, but cannot:
-   Write or Edit files
-   Execute shell commands (`Shell` / `Bash`)
-   Run Zrb tasks
-   Spawn sub-agents

---

## How it Works

Plan Mode is an ambient state propagated via `ContextVars`. When active, `get_effective_policy()` returns the hardcoded `PLAN_MODE_POLICY`, overriding any task-level or global policy.

---

## Toggling Plan Mode

You can toggle Plan Mode on/off in two ways:

1.  **Slash Command:** Type `/plan` in the chat UI. The command toggles — type `/plan` once to enter Plan Mode, again to exit.
2.  **Keyboard Shortcut:** Press `Ctrl+P` to toggle Plan Mode at any time.

When Plan Mode is active, the info bar displays `PLAN MODE: On` (blue). When off, it displays `PLAN MODE: Off` (green).

### Tool Call

The LLM can also toggle Plan Mode via the `EnterPlanMode` and `ExitPlanMode` tools. These set the mode programmatically (non-toggling).

---

## Security: The Strict ASK Gate

Exiting Plan Mode is a high-risk transition because it opens the execution gate. To protect against unauthorized "escapes," the `ExitPlanMode` tool is protected by a **Strict ASK** rule in the `PLAN_MODE_POLICY`.

**This means:**
-   The user **must** always manually approve the transition.
-   The transition **cannot** be auto-approved, even if YOLO mode is ON.
-   The user has the opportunity to review the proposed plan before any execution begins.

---

🔖 [Home](../../README.md) > [Advanced Topics](./) > Plan Mode
