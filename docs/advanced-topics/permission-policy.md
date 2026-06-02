🔖 [Home](../../README.md) > [Advanced Topics](./) > Permission Policy

# Permission Policy System

Zrb includes a robust, first-match-wins permission system designed to provide fine-grained control over which tools an LLM agent can call. This system acts as a security gate, ensuring that agents operate within safe boundaries even when YOLO mode is enabled.

---

## Table of Contents

- [Overview](#overview)
- [How it Works](#how-it-works)
- [Defining a Policy](#defining-a-policy)
- [The Precedence Chain](#the-precedence-chain)
- [Strict ASK (YOLO Override)](#strict-ask-yolo-override)
- [Configuration](#configuration)

---

## Overview

The Permission Policy system allows you to define rules based on **Capabilities** (e.g., `READ`, `EDIT`, `EXECUTE`) and **Tool Names**. Each rule specifies an action: `ALLOW`, `DENY`, or `ASK`.

- **`ALLOW`**: The tool call is automatically approved (auto-YOLO for this specific case).
- **`DENY`**: The tool call is blocked silently; the model receives a "Blocked" message, and no user prompt is shown.
- **`ASK`**: The user must explicitly approve the tool call via the UI or approval channel.

---

## How it Works

The system evaluates tool calls through an **Execution Gate** before they are actually invoked.

```mermaid
graph TD
    A[LLM Tool Call] --> B{Execution Gate}
    B -->|MATCH: DENY| C[Block + Return Error to LLM]
    B -->|MATCH: ALLOW| D[Execute Immediately]
    B -->|MATCH: ASK| E[Prompt User for Approval]
    B -->|NO MATCH| F{YOLO Enabled?}
    F -->|Yes| D
    F -->|No| E
```

### Capabilities

Tools are tagged with capabilities in `src/zrb/llm/permission/capability.py`:

| Capability | Description | Example Tools |
|------------|-------------|---------------|
| `READ` | Pure-read operations | `Read`, `LS`, `Glob`, `Grep` |
| `EDIT` | Filesystem mutation | `Write`, `Edit`, `RM`, `MV` |
| `EXECUTE` | Arbitrary side effects | `Bash`, `RunZrbTask` |
| `NETWORK` | Outbound network access | `SearchInternet`, `OpenWebPage` |
| `DELEGATE` | Spawning sub-agents | `DelegateToAgent` |
| `META` | Harness control | `WriteTodos`, `AskUserQuestion` |

---

## Defining a Policy

A `PermissionPolicy` is an ordered tuple of `Rule` objects.

```python
from zrb.llm.permission import PermissionPolicy, Rule, ALLOW, DENY, ASK, Capability

my_policy = PermissionPolicy((
    # Deny editing any .env or .git files
    Rule("Edit", DENY, arg_pattern="**/.env"),
    Rule("Edit", DENY, arg_pattern="**/.git/**"),
    
    # Allow all reads
    Rule(Capability.READ, ALLOW),
    
    # Force confirmation for all shell commands
    Rule("Bash", ASK),
    
    # Deny everything else by default
    Rule("*", DENY)
))
```

### Rule Matching

Rules can match on:
1.  **Exact Tool Name:** e.g., `"Bash"`, `"Write"`.
2.  **Capability:** e.g., `Capability.EDIT`.
3.  **Wildcard:** `"*"` matches everything.
4.  **Arg Pattern:** An optional glob pattern matched against salient arguments (like `path` or `command`).

---

## The Precedence Chain

When pydantic-ai requests a tool call, Zrb resolves the outcome using this priority order (ADR-0055):

1.  **Permission Policy:** If a rule matches, its action (`ALLOW`/`DENY`/`ASK`) is final.
2.  **Tool Policy:** (Legacy middleware layer)
3.  **YOLO Toggle:** If YOLO is ON, the call is approved.
4.  **Approval Channel:** Remote/multi-channel handlers.
5.  **CLI Fallback:** User is prompted in the terminal.

---

## Strict ASK (YOLO Override)

A critical security feature of the system is the **Strict ASK** behavior. 

If a Permission Policy explicitly returns `ASK` for a tool call, the system **ignores the YOLO toggle** and forces a manual confirmation. This ensures that high-risk transitions (like exiting [Plan Mode](./plan-mode.md)) can never be automated away by a model.

---

## Configuration

You can set the default policy globally or per-task.

### Global Configuration

```bash
export ZRB_LLM_PERMISSIONS="READ:allow,EDIT:ask,EXECUTE:ask,*:deny"
```

### Per-Task Configuration

```python
from zrb import LLMChatTask, cli

safe_task = cli.add_task(
    LLMChatTask(
        name="safe-chat",
        permissions=my_policy # Use the policy object defined above
    )
)
```

---
🔖 [Home](../../README.md) > [Advanced Topics](./) > Permission Policy
