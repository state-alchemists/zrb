# Agent-in-a-Pipeline Example

This example demonstrates the capability that sets Zrb's agent apart from a config-driven assistant: **an `LLMTask` is an ordinary task, so it can sit inside a DAG** between deterministic steps, with a **custom tool that calls into your own code in-process**.

## How it works

A three-step ticket-triage pipeline:

```
intake  →  triage (LLM + custom tool)  →  route
```

| Step | Type | What it does |
|---|---|---|
| `intake` | `Task` | Produces a raw support ticket. Its return value is auto-pushed to XCom. |
| `triage` | `LLMTask` | Reads the ticket from XCom, calls the `lookup_customer` tool to check the plan tier, and returns a structured verdict. |
| `route` | `Task` | Pops the verdict from XCom and acts on it. |

Two things to notice:

1. **The agent calls *your* Python.** `lookup_customer` is a plain function querying an in-process dict (stand-in for your CRM/DB). The model can only reach that data through the tool you gave it — no subprocess, no MCP server, no separate SDK.
2. **Data flows through [XCom](../../docs/core-concepts/session-and-context.md).** `intake`'s return becomes the agent's input via `{ctx.xcom['intake'].peek()}` in its `message`; the agent's answer becomes `route`'s input via `ctx.xcom['triage'].pop()`. The `>>` operator wires the dependency order.

## Running the example

```bash
cd examples/agent-in-pipeline
export OPENAI_API_KEY="your-key-here"   # or configure any other provider
zrb triage route
```

Zrb runs `intake` → `triage` → `route` in order. Expected output ends with something like:

```
Routing based on the agent's verdict:
PRIORITY: P1
TEAM: oncall
```

(Acme Corp is on the `enterprise` plan and reports an outage, so the rule forces P1.)

## Try it

- Change the ticket in `intake` to mention `C-2002` (a `free`-plan customer) and watch the priority change.
- Swap the printed routing in `route` for a real action — page oncall, open a ticket, send a Slack message.
- Add a fourth step downstream that only runs when `PRIORITY: P1`, using an `execute_condition`.

See **[Programming the Agent](../../docs/advanced-topics/programming-the-agent.md)** for the full set of hooks you can program in Python.
