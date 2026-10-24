"""A lazy registration can be configured before it loads.

The stand-in exists so a built-in task's module is not imported by every
command. That deferral used to stop a registration site from adding anything to
the task: the tool, the hook, the policy all need the task to exist, so the site
imported it and paid the cost the stand-in was there to avoid.

`on_resolve` moves the work to the task's own load. Three properties matter and
each fails silently on its own: the callback does not run at registration, it
runs before the first caller sees the task, and it never runs twice.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zrb.task.lazy_task import LazyTask

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src"


def _stand_in() -> LazyTask:
    """A stand-in for a built-in task whose module is cheap to import."""
    return LazyTask(
        name="now",
        description="🕰️ Get current time",
        module="zrb.builtin.datetime",
        attribute="now",
    )


def _clean_env() -> dict[str, str]:
    """A near-empty environment, so the developer's own knobs cannot steer it."""
    env = {"PYTHONPATH": str(SRC), "HOME": str(Path.home())}
    env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    if sys.platform == "win32":
        for name in ("SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "TEMP"):
            value = os.environ.get(name)
            if value is not None:
                env[name] = value
    return env


def _probe(code: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_clean_env(),
    )
    assert result.returncode == 0, f"the probe failed: {result.stderr[-2000:]}"
    return json.loads(result.stdout)


def test_a_callback_waits_for_the_task_to_load():
    seen: list[str] = []

    stand_in = _stand_in().on_resolve(lambda task: seen.append(task.name))

    # Assert
    assert seen == [], "The callback ran at registration, before the task existed."
    stand_in.resolve()
    assert seen == ["now"], f"The callback saw {seen}, not the resolved task."


def test_a_callback_runs_in_registration_order():
    seen: list[str] = []

    stand_in = _stand_in()
    stand_in.on_resolve(lambda _task: seen.append("first"))
    stand_in.on_resolve(lambda _task: seen.append("second"))

    stand_in.resolve()

    assert seen == ["first", "second"]


def test_on_resolve_is_chainable():
    stand_in = _stand_in()

    assert stand_in.on_resolve(lambda _task: None) is stand_in


def test_registering_after_the_task_loaded_applies_immediately():
    """A dispatch may have resolved the stand-in before an init script ran."""
    seen: list[str] = []
    stand_in = _stand_in()
    stand_in.resolve()

    stand_in.on_resolve(lambda task: seen.append(task.name))

    assert seen == ["now"], "A late callback was queued and will never run."


def test_a_callback_runs_once_across_repeated_resolves():
    calls: list[str] = []
    stand_in = _stand_in().on_resolve(lambda task: calls.append(task.name))

    stand_in.resolve()
    stand_in.resolve()

    assert calls == ["now"]


def test_a_failing_callback_is_retried_rather_than_cached():
    """Nothing half-configured may be handed out to the next caller."""
    attempts: list[int] = []

    def flaky(_task) -> None:
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise RuntimeError("misconfigured")

    stand_in = _stand_in().on_resolve(flaky)

    # Act
    with pytest.raises(RuntimeError, match="misconfigured"):
        stand_in.resolve()

    # Assert
    assert stand_in.resolve() is not None
    assert attempts == [1, 2], "The callback was dropped after raising once."


def test_a_callback_that_succeeded_is_not_replayed_after_a_later_failure():
    """Replaying it would append the same tool to the task twice."""
    calls: list[str] = []

    def first(_task) -> None:
        calls.append("first")

    def second(_task) -> None:
        calls.append("second")
        if calls.count("second") == 1:
            raise RuntimeError("misconfigured")

    stand_in = _stand_in().on_resolve(first).on_resolve(second)

    # Act
    with pytest.raises(RuntimeError, match="misconfigured"):
        stand_in.resolve()
    stand_in.resolve()

    # Assert
    assert calls == ["first", "second", "second"]


def test_configuring_the_chat_stand_in_does_not_import_its_module():
    """The whole point: the customization costs what the deferral saved."""
    state = _probe(
        "import json, sys; import zrb.builtin; "
        "from zrb.builtin.llm.deferred import llm_chat; "
        "seen = []; llm_chat.on_resolve(lambda task: seen.append(task.name)); "
        "print(json.dumps({"
        "'loaded': 'zrb.builtin.llm.chat' in sys.modules, 'seen': seen}))"
    )

    # Assert
    assert state["loaded"] is False, (
        "Registering a callback on the stand-in imported "
        "`zrb.builtin.llm.chat`, which is the import the stand-in defers."
    )
    assert state["seen"] == [], "The callback ran before anything needed the task."


def test_the_chat_module_loads_when_something_needs_it():
    state = _probe(
        "import json, sys; import zrb.builtin; "
        "from zrb.builtin.llm.deferred import llm_chat; "
        "seen = []; llm_chat.on_resolve(lambda task: seen.append(task.name)); "
        "task = llm_chat.resolve(); "
        "print(json.dumps({"
        "'loaded': 'zrb.builtin.llm.chat' in sys.modules, "
        "'seen': seen, 'resolved': task.name}))"
    )

    # Assert
    assert state["loaded"] is True
    assert state["seen"] == ["chat"], "The callback did not run at load time."
    assert state["resolved"] == "chat"
