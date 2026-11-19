"""The task a resumed delegated session runs as, built in a third unit.

`subagent/` cannot name `task/` (the chat task reaches the manager for its
roster and its `@mentions`, so the import back is a cycle), and `task/` cannot
be asked to register itself either — that leaves a manager method that raises
for any caller who never loaded the chat task. So `resumed_session.py` names
the task, `subagent/` names it, and the import waits until a session is
actually resumed.
"""

import os
import subprocess
import sys
from pathlib import Path

from zrb.llm.orchestration.resumed_session import create_resumed_chat_task
from zrb.llm.contracts.shared.sub_agent_build import SubAgentBuild

_SRC = Path(__file__).resolve().parents[3] / "src"

# What a library has: the manager, and nothing that builds the chat task. The
# lazy import used to live inside `create_llm_chat_task` itself, so a caller
# outside the web route got a task; it has to keep doing that.
_LIBRARY_CALLER_PROBE = """
import sys

import zrb.llm.orchestration.subagent.building as building
from zrb.llm.orchestration.subagent.definition import SubAgentDefinition
from zrb.llm.orchestration.subagent.manager.manager import sub_agent_manager

assert "zrb.llm.orchestration.task.chat.task" not in sys.modules, "probe must start without it"
building.resolve_configured_model = lambda *args, **kwargs: "probe-model"
sub_agent_manager.add_agent(
    SubAgentDefinition(
        name="probe-agent",
        path=".",
        description="probe",
        system_prompt="You are a probe.",
        tools=[],
        model="probe-model",
    )
)
task = sub_agent_manager.create_llm_chat_task("probe-agent")
print(type(task).__name__, task.name, "zrb.llm.orchestration.task.chat.task" in sys.modules)
"""


def test_a_build_becomes_the_task_a_session_runs_as():
    task = create_resumed_chat_task(
        SubAgentBuild(
            model="some-model",
            system_prompt="You are a probe.",
            tools=[],
            toolsets=[],
            yolo=False,
        ),
        "probe-agent",
        "probe",
    )

    assert type(task).__name__ == "LLMChatTask"
    assert task.name == "resumed-probe-agent"


def test_a_library_caller_resumes_with_no_chat_task_loaded_yet():
    """The public manager method keeps its old behaviour: it loads what it needs.

    It used to import `LLMChatTask` lazily inside itself. That import is now in
    `resumed_session.py`, one unit across, and it still happens at the same
    moment — so a process that only ever imported the manager gets a task
    rather than a refusal.
    """
    result = subprocess.run(
        [sys.executable, "-c", _LIBRARY_CALLER_PROBE],
        capture_output=True,
        text=True,
        cwd=_SRC.parent,
        env={**os.environ, "PYTHONPATH": str(_SRC)},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["LLMChatTask", "resumed-probe-agent", "True"]
