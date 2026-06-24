"""
Programmable Live Context Example

Demonstrates `prompt_manager.add_live_context(name, provider)` — injecting
volatile, per-turn runtime state into the `<live-context>` block that is
appended to every user message.

Unlike `register_section` (which adds to the CACHED system prompt), live-context
providers run every turn and carry state that changes between turns WITHOUT
invalidating the cacheable prompt prefix. That makes them the right tool for
"what is true right now" facts: current time, a deploy-freeze flag, the active
incident, queue depth, etc.

Here we add two providers to the built-in `llm_chat` task:

1. `wall_clock`     — the current local time (proves the block changes per turn).
2. `deploy_freeze`  — reads the ZRB_DEPLOY_FROZEN env var EACH turn, so flipping
                      it mid-session changes the agent's behavior with no restart.

Usage:
    cd examples/live-context
    zrb llm chat
    > What time is it according to your live context?
    # in another shell: export ZRB_DEPLOY_FROZEN=true   (then ask again)
    > Are deploys allowed right now?
"""

import os
from datetime import datetime

from zrb.builtin.llm.chat import llm_chat

# =============================================================================
# Provider 1: wall clock — recomputed every turn.
# =============================================================================


def render_wall_clock(ctx) -> str:
    """Return a live-context line with the current local time.

    The provider receives the active context and returns a string. Returning
    "" or None emits nothing for that turn.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"- Current time: {now}"


# =============================================================================
# Provider 2: deploy-freeze flag — read from the environment each turn.
# =============================================================================


def render_deploy_freeze(ctx) -> str:
    """Reflect a runtime flag the agent should respect on every turn.

    Because this runs per turn, toggling ZRB_DEPLOY_FROZEN in the environment
    takes effect on the very next message — no restart, and the cached system
    prompt prefix is untouched.
    """
    frozen = os.environ.get("ZRB_DEPLOY_FROZEN", "").lower() in ("1", "true", "yes")
    if frozen:
        return "- ⚠️ DEPLOY FREEZE ACTIVE: do not run or suggest any deployment."
    return "- Deploys: allowed."


# =============================================================================
# Register both providers on the built-in chat task's prompt manager.
#
# Providers run in registration order, AFTER the built-in live-context lines
# (time, git, worktree, mode, todos). Re-registering the same name replaces the
# previous provider.
# =============================================================================

llm_chat.prompt_manager.add_live_context("wall_clock", render_wall_clock)
llm_chat.prompt_manager.add_live_context("deploy_freeze", render_deploy_freeze)
