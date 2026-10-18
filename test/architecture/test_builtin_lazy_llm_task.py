"""The chat task is registered without importing the stack that builds it.

Every command imports `zrb.builtin`, so the chat task's module — an
`LLMChatTask` built out of pydantic and pydantic-ai — used to be paid by every
run: measured at ~0.21s of the ~0.30s `zrb --help` costs, and ~0.53s -> ~0.28s
for the listing once the module is deferred.

Three things have to hold at once, and each one fails silently on its own:

- `import zrb.builtin` loads no `zrb.llm` module. A single module-level import
  in any built-in module brings the whole tree back; `changelog.py` had one.
- The CLI still lists the task, in the `llm` group and as the top-level alias.
  A stand-in that registers nowhere drops the group from `--help` with exit 0.
- The stand-in agrees with the task it stands for. Its name, description and
  `cli_only` are copies, because reading them from the real task is exactly the
  import being deferred.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src"


def _clean_env() -> dict[str, str]:
    """A near-empty environment, so the developer's own knobs cannot steer it.

    Windows needs a handful of its own variables inside that minimum: zrb's
    import chain reaches `asyncio`, which loads `_overlapped` there and dies
    with `WinError 10106` without `SYSTEMROOT`.
    """
    env = {"PYTHONPATH": str(SRC), "HOME": str(Path.home())}
    if sys.platform != "win32":
        env["PATH"] = "/usr/bin:/bin"
        return env
    for name in (
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "COMSPEC",
        "PATHEXT",
        "PATH",
        "TEMP",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
    ):
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    return env


def _probe(code: str) -> dict:
    """Run *code* in a fresh interpreter importing this tree, and read its JSON."""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_clean_env(),
    )
    assert result.returncode == 0, f"the probe failed: {result.stderr[-2000:]}"
    return json.loads(result.stdout)


def test_importing_the_builtins_loads_no_llm_module():
    loaded = _probe(
        "import json, sys, zrb.builtin; print(json.dumps(sorted("
        "m for m in sys.modules if m == 'zrb.llm' or m.startswith('zrb.llm.'))))"
    )
    # Assert
    assert loaded == [], (
        f"`import zrb.builtin` now loads {len(loaded)} `zrb.llm` module(s), "
        f"starting with {loaded[:3]}. Every command pays for them, `zrb --help` "
        "included. Move the import into the code that needs it (and tag it "
        "`# lazy:`), or register the task through `builtin/llm/deferred.py`."
    )


def test_the_cli_lists_the_chat_task():
    listing = _probe(
        "import json; import zrb.__main__; "
        "from zrb.builtin.group import llm_group; "
        "from zrb.runner.cli import cli; "
        "print(json.dumps({"
        "'llm': {alias: task.description for alias, task in "
        "llm_group.get_subtasks().items()}, "
        "'root': [alias for alias in ('chat', 'please') "
        "if cli.get_task_by_alias(alias) is not None]}))"
    )
    # Assert
    assert set(listing["llm"]) == {"chat", "please"}, (
        "The `llm` group no longer lists both of its tasks: "
        f"{sorted(listing['llm'])}. A lazily registered task that is not "
        "registered on the group disappears from `--help` with exit code 0."
    )
    assert listing["root"] == ["chat", "please"], (
        f"The top-level aliases are {listing['root']}, not ['chat', 'please']. "
        "`zrb.builtin.llm.chat` registers `zrb chat` on purpose, and the "
        "stand-in has to repeat every registration the real module makes."
    )
    assert all(listing["llm"].values()), "A listed task has an empty description."


def test_the_stand_in_agrees_with_the_task_it_stands_for():
    agreement = _probe(
        "import json; import zrb.builtin; "
        "from zrb.builtin.group import llm_group; "
        "stand_in = llm_group.get_task_by_alias('chat'); "
        "real = zrb.builtin.llm_chat; "
        "print(json.dumps({"
        "'stand_in': [type(stand_in).__name__, stand_in.name, "
        "stand_in.description, stand_in.is_cli_only], "
        "'real': [type(real).__name__, real.name, real.description, "
        "real.is_cli_only], "
        "'group_holds_the_real_task': "
        "llm_group.get_task_by_alias('chat') is real}))"
    )
    # Assert
    assert agreement["stand_in"][0] == "LazyTask", (
        "The tree already holds the real task, so this test cannot see the "
        "stand-in: something imported the chat module before `zrb --help` "
        "needed it, which is the cost this deferral removes."
    )
    assert agreement["real"][0] == "LLMChatTask", (
        f"Resolving the stand-in returned a {agreement['real'][0]}, not the "
        "task `zrb.builtin.llm.chat` declares."
    )
    assert agreement["stand_in"][1:] == agreement["real"][1:], (
        "The stand-in and the task it stands for disagree.\n"
        f"stand-in: {agreement['stand_in'][1:]}\nreal:     {agreement['real'][1:]}\n"
        "Copy the real declaration into `builtin/llm/deferred.py`."
    )
    assert agreement["group_holds_the_real_task"], (
        "Resolving the stand-in left it registered, so the next dispatch would "
        "resolve it again instead of using the task the module registered."
    )


def test_shadowing_the_chat_task_is_not_reported_as_a_collision():
    """A project task replacing `zrb chat` is an intended shadow, not a clash.

    The snapshot `zrb/__main__.py` takes holds the stand-in, so the real task
    registers after it. Without `mark_builtin_task`, replacing the real task
    looks like two of the project's own tasks fighting over one alias.
    """
    diagnostics = _probe(
        "import json; import zrb.__main__; import zrb.builtin.llm.chat; "
        "from zrb.builtin.group import llm_group; "
        "from zrb.group.task_diagnostics import find_task_diagnostics, "
        "get_builtin_task_ids; "
        "from zrb.runner.cli import cli; "
        "from zrb.task.base.base_task import BaseTask; "
        "llm_group.add_task(BaseTask(name='chat')); "
        "print(json.dumps([d.problem for d in find_task_diagnostics("
        "[], cli, get_builtin_task_ids())]))"
    )
    # Assert
    assert diagnostics == [], (
        f"The CLI would warn about {diagnostics} on a run that shadows the "
        "built-in chat task. `zrb.builtin.llm.chat` must call "
        "`mark_builtin_task` after it builds the task."
    )


def test_resolve_task_leaves_an_ordinary_task_alone():
    from zrb.task.base.base_task import BaseTask
    from zrb.task.lazy_task import resolve_task

    task = BaseTask(name="plain")

    # Act
    resolved = resolve_task(task)

    # Assert
    assert resolved is task


def test_resolving_a_lazy_task_is_cached():
    from zrb.task.lazy_task import LazyTask, resolve_task

    stand_in = LazyTask(
        name="chat",
        description="🤖 Chat with your AI Assistant",
        module="zrb.builtin.llm.chat",
        attribute="llm_chat",
    )

    # Act
    first, second = resolve_task(stand_in), stand_in.resolve()

    # Assert
    assert first is second
    assert first.name == "chat"


def test_resolving_a_lazy_task_pointing_nowhere_fails_loudly():
    from zrb.task.lazy_task import LazyTask

    stand_in = LazyTask(
        name="chat",
        description="🤖 Chat with your AI Assistant",
        module="zrb.builtin.llm.chat",
        attribute="not_a_task",
    )

    # Act
    with pytest.raises(ImportError, match="not_a_task"):
        stand_in.resolve()


def test_an_unresolved_lazy_task_refuses_to_run():
    from zrb.task.lazy_task import LazyTask

    stand_in = LazyTask(
        name="chat",
        description="🤖 Chat with your AI Assistant",
        module="zrb.builtin.llm.chat",
        attribute="llm_chat",
    )

    # Act
    with pytest.raises(RuntimeError, match="lazy registration"):
        stand_in.run()
