🔖 [Documentation Home](../../README.md) > [LLM](./) > Plan Mode

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

When an agent is in Plan Mode, it is restricted by the `PLAN_MODE_POLICY`. This policy permits all `READ`, `NETWORK`, and `META` (harness control, e.g. `TodoWrite`) operations but strictly denies `EDIT`, `EXECUTE`, and `DELEGATE` capabilities — and any untagged (`UNKNOWN`) tool, such as an MCP tool.

This ensures that the agent can read files, search the internet, and analyze code, but cannot:
-   Write or Edit files
-   Execute shell commands (`Shell`)
-   Run Zrb tasks
-   Spawn sub-agents

---

## How it Works

Plan Mode is an ambient state propagated via `ContextVars`. When active, `get_effective_policy()` returns the hardcoded `PLAN_MODE_POLICY`, overriding any task-level or global policy.

---

## Toggling Plan Mode

You can toggle Plan Mode on/off in two ways:

1.  **Slash Command:** Type `/plan` in the chat UI. The command toggles — type `/plan` once to enter Plan Mode, again to exit.
2.  **Keyboard Shortcut:** Press `Shift+Tab` (plain `Tab` on Termux) to cycle through modes: `normal` → `accept-edits` → `plan` → back to `normal`. (This is a 3-way cycle, not a simple plan on/off toggle. `Ctrl+Y` toggles YOLO mode instead, which is unrelated to Plan Mode.)

The status bar shows the current mode as a badge (`normal`, `accept-edits`, `plan`, ...). `/plan` also prints `📋 PLAN MODE: On` / `📋 PLAN MODE: Off` in the output. The command name is configurable via `ZRB_LLM_UI_COMMAND_PLAN_TOGGLE` (default `/plan`).

### Tool Call

The LLM can also toggle Plan Mode via the `EnterPlanMode` and `ExitPlanMode` tools. These set the mode programmatically (non-toggling). Both tools are registered only in interactive sessions.

---

## Security: The Strict ASK Gate

Exiting Plan Mode is a high-risk transition because it opens the execution gate. To protect against unauthorized "escapes," the `ExitPlanMode` tool is protected by a **Strict ASK** rule in the `PLAN_MODE_POLICY`.

**This means:**
-   The user **must** always manually approve the transition.
-   The transition **cannot** be auto-approved, even if YOLO mode is ON.
-   The user has the opportunity to review the proposed plan before any execution begins.

The one exception is a non-interactive run (`--interactive false`), where there is no user to ask: `ExitPlanMode` is then approved automatically, and every other approval-gated tool is denied.

---

🔖 [Documentation Home](../../README.md) > [LLM](./) > Plan Mode
