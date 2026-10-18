"""Registers the LLM chat task without importing the stack that builds it.

Every `zrb` run imports `zrb.builtin`, so `zrb.builtin.llm.chat` — which
constructs an `LLMChatTask` out of pydantic, pydantic-ai and the whole
`zrb.llm` tree — would be paid by every command, `zrb --help` included,
measured at ~0.21s of the ~0.30s a help listing costs.

The task is registered here as a `LazyTask` stand-in instead: the CLI tree reads
its name and description, and `Group.extract_node` imports the real module the
moment a command line addresses it. `name` and `description` are copies of
`zrb/builtin/llm/chat.py`'s declaration, pinned by
`test/architecture/test_builtin_lazy_llm_task.py`.
"""

from zrb.builtin.group import llm_group
from zrb.runner.cli import cli
from zrb.task.lazy_task import LazyTask

llm_chat = LazyTask(
    name="chat",
    description="🤖 Chat with your AI Assistant",
    module="zrb.builtin.llm.chat",
    attribute="llm_chat",
)

# The same two registrations `zrb.builtin.llm.chat` makes once it is imported:
# under the `llm` group, and as the top-level `zrb chat` alias.
llm_group.add_task(llm_chat)
cli.add_task(llm_chat)
