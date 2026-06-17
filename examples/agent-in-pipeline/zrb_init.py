"""
Agent-in-a-Pipeline Example

Shows the thing a config-driven assistant can't do: an LLM agent as one node
in a deterministic DAG. A plain task fetches work, the agent reasons over it
(calling a tool that reaches into your own code in-process), and another plain
task acts on the verdict. Data flows between them through XCom.

    intake  →  triage (LLM + custom tool)  →  route

Usage:
    cd examples/agent-in-pipeline
    export OPENAI_API_KEY="your-key-here"   # or configure any other provider
    zrb triage route
"""

from zrb import Group, LLMTask, Task, cli

# =============================================================================
# Your in-process "systems". The agent can only reach this through a tool —
# in real life it would be your CRM, database, or an internal API client.
# =============================================================================

_CUSTOMERS = {
    "C-1001": {"name": "Acme Corp", "plan": "enterprise"},
    "C-2002": {"name": "Hobby Joe", "plan": "free"},
}


async def lookup_customer(customer_id: str) -> str:
    """Look up a customer account by id. Returns the account name and plan tier."""
    customer = _CUSTOMERS.get(customer_id)
    if customer is None:
        return f"No customer found for id {customer_id!r}."
    return f"{customer['name']} — plan: {customer['plan']}"


# =============================================================================
# The pipeline
# =============================================================================

triage_group = cli.add_group(Group(name="triage", description="🎫 Ticket triage demo"))

# 1. Deterministic intake. Hard-coded here; in production you'd pull from your
#    queue / inbox / webhook. A task's return value is auto-pushed to XCom.
intake = triage_group.add_task(
    Task(
        name="intake",
        action=lambda ctx: (
            "Customer C-1001 writes: 'Our production API has been down for 20 "
            "minutes and we are losing orders.' Please triage this ticket."
        ),
    )
)

# 2. The agent. It reads the ticket from XCom, calls your in-process tool to
#    enrich it, and returns a structured verdict (which also lands in XCom).
triage = triage_group.add_task(
    LLMTask(
        name="triage",
        description="Triage an incoming support ticket",
        message=(
            "A support ticket arrived:\n\n{ctx.xcom['intake'].peek()}\n\n"
            "Use the lookup_customer tool to check the customer's plan, then "
            "reply with exactly two lines and nothing else:\n"
            "PRIORITY: <P1|P2|P3>\n"
            "TEAM: <oncall|support|billing>\n"
            "Rule: enterprise customers reporting an outage are always P1."
        ),
        tools=[lookup_customer],
    )
)

# 3. Deterministic routing. Acts on the agent's verdict — here it just prints,
#    but this is where you'd page oncall, open a Jira ticket, etc.
def route(ctx):
    verdict = ctx.xcom["triage"].pop()
    ctx.print("Routing based on the agent's verdict:")
    ctx.print(verdict)


route_task = triage_group.add_task(Task(name="route", action=route))

# Wire the DAG: intake → triage → route
intake >> triage >> route_task
