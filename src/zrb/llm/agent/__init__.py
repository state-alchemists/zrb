from zrb.llm.agent.common import create_agent
from zrb.llm.agent.run.runner import (
    AnyToolConfirmation,
    run_agent,
)
from zrb.llm.agent.summarizer import create_summarizer_agent

__all__ = [
    "AnyToolConfirmation",
    "create_agent",
    "run_agent",
    "create_summarizer_agent",
]

# Registers the HookType.AGENT builder (zrb.llm.hook.agent_hook_registry) as a
# side effect of loading the agent package. Every real entry point already
# imports zrb.llm.agent before any hook manager scans hook files (LLMTask,
# LLMChatTask, and SubAgentManager all import from here at module load), so
# this always runs before the registry is ever read from a real process.
from zrb.llm.agent import hook_agent  # noqa: F401
