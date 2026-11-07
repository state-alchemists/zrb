"""The no-UI fallback must not drag in the presentation layer.

`resolve_context_dependencies` falls back to `StdUI` when a run has no UI.
`StdUI` lives inside the presentation package, in `ui/fallback/`, so
`zrb/llm/ui/__init__.py` resolves every export through PEP 562 instead of
importing one: the package node enters `sys.modules` the moment the fallback
loads, and an eager re-export there would put the terminal client, the base UI
and prompt_toolkit back into a headless run's import graph. The probe runs in a
clean interpreter because this test session has already imported the UI package.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[4]
SRC = REPO_ROOT / "src"

# What a bare interpreter needs from the parent: PATH to start at all, plus the
# variables Windows requires to load its own runtime.
_INHERITED = (
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "COMSPEC",
    "PATHEXT",
    "PATH",
    "TEMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
)

_NO_UI_FALLBACK_PROBE = """
import sys

from zrb.llm.agent.run.setup import resolve_context_dependencies
from zrb.llm.ui.fallback.resolution import get_main_ui
from zrb.llm.ui.fallback.std_ui import StdUI

PRESENTATION = ("zrb.llm.ui.base", "zrb.llm.ui.default", "zrb.llm.ui.multi_ui",
                "prompt_toolkit")


def loaded_presentation():
    return sorted(name for name in sys.modules if name.startswith(PRESENTATION))


assert not loaded_presentation(), f"presentation loaded early: {loaded_presentation()}"
plain_ui = StdUI()
assert get_main_ui(plain_ui) is plain_ui, "an unregistered UI is its own main UI"

ui, *_ = resolve_context_dependencies(None, None, None, None, None)
assert isinstance(ui, StdUI), type(ui)
assert not loaded_presentation(), f"the fallback loaded the presentation: {loaded_presentation()}"
print("ok")
"""

_UNREGISTERED_COMBINER_PROBE = """
from zrb.llm.ui.fallback.resolution import create_combined_ui
from zrb.llm.ui.fallback.std_ui import StdUI

try:
    create_combined_ui([StdUI(), StdUI()], fallback=StdUI())
except RuntimeError as error:
    assert "[SYSTEM SUGGESTION]" in str(error), error
    print("ok")
else:
    raise AssertionError("expected a suggestion")
"""


def _run_in_clean_interpreter(code: str) -> str:
    """Run *code* in a fresh interpreter that imports this tree, not an install."""
    env = {"PYTHONPATH": str(SRC), "HOME": str(Path.home())}
    env.update({name: os.environ[name] for name in _INHERITED if name in os.environ})
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, f"the probe failed: {result.stderr[-2000:]}"
    return result.stdout


def test_the_no_ui_fallback_does_not_load_the_presentation_package():
    output = _run_in_clean_interpreter(_NO_UI_FALLBACK_PROBE)
    assert output.strip() == "ok"


def test_several_uis_without_the_presentation_package_explain_themselves():
    """A list of two or more needs the registered combiner; say so clearly."""
    output = _run_in_clean_interpreter(_UNREGISTERED_COMBINER_PROBE)
    assert output.strip() == "ok"
